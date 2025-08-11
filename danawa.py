# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from typing import List, Dict, Optional, Tuple
from io import BytesIO

class DanawaParser:
    """
    다나와 검색 파서
    - 키워드로 검색 페이지를 열어 '제조사' 옵션(숫자 코드)을 추출
    - 제조사 코드(maker=702,4213,...)를 붙여 다시 검색
    - 제품명/가격/스펙을 파싱하여 표로 반환
    """
    BASE_URL = "https://search.danawa.com/mobile/dsearch.php"
    HEADERS = {
        # 모바일 UA가 셀렉터 호환성이 보통 더 좋습니다.
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Pixel 3) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # 스펙/가격 파싱 시 잠재적 셀렉터 후보들을 여러 개 두고 순차 확인
    SELECTOR_CANDIDATES = {
        "item": [
            "div.product_item",              # 예시
            "div.product-list__item",        # 예시
            "li.search_prod_item",           # 예시
            "div.prod_item"                  # 예시
        ],
        "name": [
            "div.tit a", "p.tit a", "a.prod_name", "a.link", "a.name"
        ],
        "price": [
            "div.price strong", "em.prc_c", "span.num", "strong.price_num"
        ],
        "spec": [
            "div.spec_list", "ul.spec_list", "p.spec", "div.spec"
        ],
    }

    # 옵션 스크랩 실패 시 아주 최소한의 기본 매핑(예시) — 필요시 추가하세요.
    FALLBACK_MAKERS = [
        {"category": "제조사", "name": "Samsung",  "code": "702"},
        {"category": "제조사", "name": "WD",       "code": "955"},
        {"category": "제조사", "name": "Seagate",  "code": "973"},
        {"category": "제조사", "name": "Kingston", "code": "4213"},
        {"category": "제조사", "name": "Crucial",  "code": "1159"},
    ]

    def __init__(self, delay: float = 0.8):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.delay = delay  # 사이트 과부하 방지 지연

    # -----------------------------
    # internal helpers
    # -----------------------------
    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"[HTTP ERROR] GET {url} params={params} -> {e}")
            return None

    @staticmethod
    def _first_text(soup: BeautifulSoup, selectors: List[str]) -> str:
        for css in selectors:
            node = soup.select_one(css)
            if node and node.get_text(strip=True):
                return node.get_text(strip=True)
        return ""

    @staticmethod
    def _first_element(soup: BeautifulSoup, selectors: List[str]):
        for css in selectors:
            node = soup.select_one(css)
            if node:
                return node
        return None

    @staticmethod
    def _to_int_price(text: str) -> Optional[int]:
        # "123,456원" → 123456
        if not text:
            return None
        m = re.findall(r"\d+", text.replace(",", ""))
        if not m:
            return None
        try:
            return int("".join(m))
        except ValueError:
            return None

    @staticmethod
    def _unique_by_key(items: List[Dict], key: str) -> List[Dict]:
        seen = set()
        out = []
        for it in items:
            val = it.get(key, "")
            if val not in seen:
                seen.add(val)
                out.append(it)
        return out

    # -----------------------------
    # options
    # -----------------------------
    def get_search_options(self, keyword: str) -> List[Dict]:
        """
        검색 키워드로 열리는 페이지에서 제조사 옵션(숫자 code)을 수집.
        - makerBrandTab / makerOptionTab 등에서 버튼의 data- 속성으로 추출
        - 비숫자(문자열) code는 필터링하여 제외
        """
        params = {
            "k1": keyword,
        }
        resp = self._get(self.BASE_URL, params=params)
        if not resp:
            print("[옵션] 초기 요청 실패 — 기본 매핑 반환")
            return self.FALLBACK_MAKERS[:]

        soup = BeautifulSoup(resp.text, "lxml")

        options: List[Dict] = []

        # 1) makerBrandTab
        brand_tab = soup.find("div", id="makerBrandTab")
        if brand_tab:
            buttons = brand_tab.find_all("button")
            for b in buttons:
                name = b.get("data-optionname", "").strip() or b.get_text(strip=True)
                code = b.get("data-optioncode", "").strip()
                if code.isdigit() and name:
                    options.append({"category": "제조사", "name": name, "code": code})

        # 2) makerOptionTab
        option_tab = soup.find("div", id="makerOptionTab")
        if option_tab:
            buttons = option_tab.find_all("button")
            for b in buttons:
                name = b.get("data-optionname", "").strip() or b.get_text(strip=True)
                code = b.get("data-optioncode", "").strip()
                if code.isdigit() and name:
                    options.append({"category": "제조사", "name": name, "code": code})

        # 혹시 다른 구조 (data-value, value)에 코드가 있을 수도 있음
        if not options:
            candidates = soup.select("button, a")
            for el in candidates:
                name = el.get("data-optionname") or el.get("title") or el.get_text(strip=True)
                code = (
                    el.get("data-optioncode")
                    or el.get("data-value")
                    or el.get("value")
                    or ""
                )
                name = (name or "").strip()
                code = (code or "").strip()
                if code.isdigit() and name:
                    options.append({"category": "제조사", "name": name, "code": code})

        # 정리: 비숫자 제거 + 중복 제거
        options = [o for o in options if str(o.get("code", "")).isdigit()]
        options = self._unique_by_key(options, "code")

        if not options:
            print("[옵션] 스크랩 결과 없음 — 기본 매핑 반환")
            return self.FALLBACK_MAKERS[:]

        return options

    # -----------------------------
    # search
    # -----------------------------
    def _build_params(self, keyword: str, maker_codes_csv: Optional[str]) -> Dict:
        """
        maker_codes_csv: '702,4213' 처럼 숫자 코드 쉼표 연결 문자열 (사전 인코딩 금지)
        """
        params = {
            "k1": keyword,
            # 필요시 더 보강: 정렬, 카테고리 등
        }
        if maker_codes_csv:
            params["maker"] = maker_codes_csv  # 쉼표 그대로 두면 requests가 적절히 인코딩
        return params

    def search_products(self, keyword: str, maker_codes: Optional[List[str]] = None) -> List[Dict]:
        """
        키워드 + (선택) 제조사 코드들의 제품 목록을 파싱하여 반환
        """
        maker_csv = None
        if maker_codes:
            # 숫자만 통과
            codes = [c for c in maker_codes if str(c).isdigit()]
            maker_csv = ",".join(codes) if codes else None

        params = self._build_params(keyword, maker_csv)
        resp = self._get(self.BASE_URL, params=params)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # 아이템 컨테이너 후보 셀렉터 중 존재하는 것을 사용
        item_nodes = []
        for css in self.SELECTOR_CANDIDATES["item"]:
            item_nodes = soup.select(css)
            if item_nodes:
                break

        results = []
        for node in item_nodes:
            name = self._first_text(node, self.SELECTOR_CANDIDATES["name"])
            price_text = self._first_text(node, self.SELECTOR_CANDIDATES["price"])
            spec_node = self._first_element(node, self.SELECTOR_CANDIDATES["spec"])
            spec_text = ""
            if spec_node:
                # li/줄바꿈을 고려해 깔끔하게 합치기
                spec_text = " ".join([t.get_text(" ", strip=True) for t in spec_node.select("*")]) \
                    if spec_node.select("*") else spec_node.get_text(" ", strip=True)

            price = self._to_int_price(price_text)

            # 최소 필드만 채우고, 없으면 빈 값. (파싱 실패해도 크래시 방지)
            if not name and not price and not spec_text:
                continue

            results.append({
                "제품명": name,
                "가격": price if price is not None else "",
                "가격(원문)": price_text,
                "스펙": spec_text
            })

        return results

    # -----------------------------
    # utilities for app
    # -----------------------------
    @staticmethod
    def to_dataframe(results: List[Dict]) -> pd.DataFrame:
        if not results:
            return pd.DataFrame(columns=["제품명", "가격", "가격(원문)", "스펙"])
        df = pd.DataFrame(results)
        # 가격 숫자 기준 정렬(있다면)
        if "가격" in df.columns:
            try:
                df["가격_num"] = pd.to_numeric(df["가격"], errors="coerce")
                df = df.sort_values(by=["가격_num", "제품명"], ascending=[True, True]).drop(columns=["가격_num"])
            except Exception:
                pass
        return df

    @staticmethod
    def to_excel_bytes(df: pd.DataFrame) -> BytesIO:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="검색결과")
        output.seek(0)
        return output

# -----------------------------
# CLI 테스트용 (로컬에서만)
# -----------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", type=str, required=True, help="검색 키워드")
    parser.add_argument("--maker", type=str, default="", help="쉼표로 구분된 제조사 코드들 (예: '702,4213')")
    args = parse
