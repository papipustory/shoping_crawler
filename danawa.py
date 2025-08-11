# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from typing import List, Dict, Optional
from io import BytesIO

class DanawaParser:
    """
    다나와 검색 파서 (모바일 검색 페이지 기준)
    - 키워드로 검색 페이지를 열어 '제조사/브랜드' 옵션(숫자 code)만 추출
    - 제조사 코드(maker=702,4213,...)를 붙여 다시 검색
    - 제품명/가격/스펙을 파싱하여 표로 반환
    - 디버그: 마지막 요청 URL, 전체 HTML, 옵션 블록 HTML 저장
    """
    BASE_URL = "https://search.danawa.com/mobile/dsearch.php"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Pixel 3) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # 제품 파싱 시 후보 셀렉터들(사이트 구조 변화 대비)
    SELECTOR_CANDIDATES = {
        "item": [
            "div.product_item",
            "div.product-list__item",
            "li.search_prod_item",
            "div.prod_item",
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

    def __init__(self, delay: float = 0.8):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.delay = delay
        # 디버그 필드
        self.last_request_url: Optional[str] = None
        self.last_html: Optional[str] = None
        self.last_option_html: Optional[str] = None

    # -----------------------------
    # HTTP
    # -----------------------------
    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        try:
            resp = self.session.get(url, params=params, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            # 실제 최종 요청 URL 저장(파라미터 포함)
            self.last_request_url = resp.url
            return resp
        except requests.RequestException as e:
            print(f"[HTTP ERROR] GET {url} params={params} -> {e}")
            return None

    # -----------------------------
    # 옵션 추출
    # -----------------------------
    def get_search_options(self, keyword: str) -> List[Dict]:
        """
        검색 키워드 페이지에서 '제조사/브랜드' 옵션(숫자 code)만 수집.
        fallback(기본 목록) 없음: 페이지에 없으면 빈 목록 반환.
        """
        resp = self._get(self.BASE_URL, params={"k1": keyword})
        if not resp:
            self.last_html = None
            self.last_option_html = None
            return []

        self.last_html = resp.text
        soup = BeautifulSoup(resp.text, "lxml")

        # 1) 명시적 maker 탭 먼저 시도
        options = self._extract_from_known_tabs(soup)
        if options:
            return options

        # 2) 제목 텍스트(제조사/브랜드 등) 기반으로 주변 블록에서 추출
        options = self._extract_from_heading_blocks(soup)
        return options

    def _extract_from_known_tabs(self, soup: BeautifulSoup) -> List[Dict]:
        options: List[Dict] = []

        def _collect_from_container(container):
            if not container:
                return
            # button 기반
            for b in container.select("button"):
                name = (b.get("data-optionname") or b.get_text(strip=True) or "").strip()
                code = (
                    b.get("data-optioncode")
                    or b.get("data-value")
                    or b.get("value")
                    or ""
                ).strip()
                if code.isdigit() and name:
                    options.append({"category": "제조사", "name": name, "code": code})
            # input[type=checkbox] 기반
            for inp in container.select('input[type="checkbox"]'):
                code = (inp.get("value") or "").strip()
                if not code.isdigit():
                    continue
                name = ""
                # for 연결된 label
                inp_id = inp.get("id")
                if inp_id:
                    lab = container.select_one(f'label[for="{inp_id}"]')
                    if lab and lab.get_text(strip=True):
                        name = lab.get_text(strip=True)
                if not name:
                    name = (inp.get("data-name") or inp.get("title") or "").strip()
                if not name:
                    # 근처 텍스트 보정
                    parent_text = inp.find_parent().get_text(" ", strip=True) if inp.find_parent() else ""
                    name = parent_text.split()[0] if parent_text else ""
                if name and code.isdigit():
                    options.append({"category": "제조사", "name": name, "code": code})

        known_ids = ["makerBrandTab", "makerOptionTab", "makerTab", "brandTab"]
        for kid in known_ids:
            cont = soup.find(id=kid)
            _collect_from_container(cont)
            if options:
                self.last_option_html = str(cont) if cont else ""
                break

        # id가 없을 수도 있으니 class에 maker/brand 포함된 컨테이너도 탐색
        if not options:
            conts = []
            for div in soup.find_all(True, {"class": True}):
                classes = " ".join(div.get("class", [])).lower()
                if "maker" in classes or "brand" in classes:
                    conts.append(div)
            for c in conts[:3]:
                _collect_from_container(c)
                if options:
                    self.last_option_html = str(c)
                    break

        # 정리: 숫자코드만, 중복 제거(code 기준)
        uniq = {}
        for o in options:
            if o["code"].isdigit() and o["name"]:
                uniq[o["code"]] = {"category": "제조사", "name": o["name"], "code": o["code"]}
        return list(uniq.values())

    def _extract_from_heading_blocks(self, soup: BeautifulSoup) -> List[Dict]:
        """
        '제조사', '브랜드', '제조사/브랜드' 같은 제목 근처에서 옵션 추출
        """
        options: List[Dict] = []

        def _collect_from_container(container):
            if not container:
                return
            # button
            for b in container.select("button"):
                name = (b.get("data-optionname") or b.get_text(strip=True) or "").strip()
                code = (
                    b.get("data-optioncode")
                    or b.get("data-value")
                    or b.get("value")
                    or ""
                ).strip()
                if code.isdigit() and name:
                    options.append({"category": "제조사", "name": name, "code": code})
            # input[type=checkbox]
            for inp in container.select('input[type="checkbox"]'):
                code = (inp.get("value") or "").strip()
                if not code.isdigit():
                    continue
                name = ""
                inp_id = inp.get("id")
                if inp_id:
                    lab = container.select_one(f'label[for="{inp_id}"]')
                    if lab and lab.get_text(strip=True):
                        name = lab.get_text(strip=True)
                if not name:
                    name = (inp.get("data-name") or inp.get("title") or "").strip()
                if not name:
                    parent_text = inp.find_parent().get_text(" ", strip=True) if inp.find_parent() else ""
                    name = parent_text.split()[0] if parent_text else ""
                if name and code.isdigit():
                    options.append({"category": "제조사", "name": name, "code": code})

        # 제목 후보 텍스트
        title_re = re.compile(r"(제조사\s*\/\s*브랜드|제조사|브랜드)")
        title_nodes = [t for t in soup.find_all(text=title_re)]

        for t in title_nodes:
            title_el = t.parent
            if not title_el:
                continue

            # 후보 컨테이너: 제목 자신 / 부모 / 다음 형제 / 부모의 다음 형제
            candidates = [
                title_el,
                title_el.parent if title_el else None,
                title_el.find_next_sibling() if title_el else None,
                title_el.parent.find_next_sibling() if title_el and title_el.parent else None,
            ]
            for cand in [c for c in candidates if c]:
                _collect_from_container(cand)
                if options:
                    self.last_option_html = str(cand)
                    break
            if options:
                break

        # 정리: 숫자 코드만, 중복 제거
        uniq = {}
        for o in options:
            if o["code"].isdigit() and o["name"]:
                uniq[o["code"]] = {"category": "제조사", "name": o["name"], "code": o["code"]}
        return list(uniq.values())

    # -----------------------------
    # 제품 검색
    # -----------------------------
    def _build_params(self, keyword: str, maker_codes_csv: Optional[str]) -> Dict:
        params = {"k1": keyword}
        if maker_codes_csv:
            params["maker"] = maker_codes_csv  # 쉼표 그대로 두면 requests가 인코딩 처리
        return params

    def search_products(self, keyword: str, maker_codes: Optional[List[str]] = None) -> List[Dict]:
        maker_csv = None
        if maker_codes:
            codes = [c for c in maker_codes if str(c).isdigit()]
            maker_csv = ",".join(codes) if codes else None

        resp = self._get(self.BASE_URL, params=self._build_params(keyword, maker_csv))
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # 아이템 컨테이너 후보
        item_nodes = []
        for css in self.SELECTOR_CANDIDATES["item"]:
            item_nodes = soup.select(css)
            if item_nodes:
                break

        results = []
        for node in item_nodes:
            # 제품명
            name = ""
            for css in self.SELECTOR_CANDIDATES["name"]:
                el = node.select_one(css)
                if el and el.get_text(strip=True):
                    name = el.get_text(strip=True)
                    break

            # 가격
            price_text = ""
            for css in self.SELECTOR_CANDIDATES["price"]:
                el = node.select_one(css)
                if el and el.get_text(strip=True):
                    price_text = el.get_text(strip=True)
                    break
            price = self._to_int_price(price_text)

            # 스펙
            spec_text = ""
            for css in self.SELECTOR_CANDIDATES["spec"]:
                el = node.select_one(css)
                if el:
                    if el.select("*"):
                        spec_text = " ".join([t.get_text(" ", strip=True) for t in el.select("*")])
                    else:
                        spec_text = el.get_text(" ", strip=True)
                    break

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
    # 유틸
    # -----------------------------
    @staticmethod
    def _to_int_price(text: str) -> Optional[int]:
        if not text:
            return None
        nums = re.findall(r"\d+", text.replace(",", ""))
        if not nums:
            return None
        try:
            return int("".join(nums))
        except ValueError:
            return None

    @staticmethod
    def to_dataframe(results: List[Dict]) -> pd.DataFrame:
        if not results:
            return pd.DataFrame(columns=["제품명", "가격", "가격(원문)", "스펙"])
        df = pd.DataFrame(results)
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

    def get_debug_dump(self) -> Dict[str, Optional[bytes]]:
        """
        스트림릿에서 다운로드 버튼에 연결할 수 있도록 Bytes 반환
        """
        return {
            "page_html": self.last_html.encode("utf-8") if self.last_html else None,
            "option_block_html": self.last_option_html.encode("utf-8") if self.last_option_html else None,
            "request_url": (self.last_request_url or "").encode("utf-8"),
        }


# CLI 테스트용
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", type=str, required=True)
    parser.add_argument("--maker", type=str, default="")
    args = parser.parse_args()

    dn = DanawaParser()
    opts = dn.get_search_options(args.keyword)
    print("[옵션수]", len(opts))
    print(opts[:10])

    makers = [m.strip() for m in args.maker.split(",") if m.strip().isdigit()] if args.maker else []
    res = dn.search_products(args.keyword, makers if makers else None)
    print("[결과수]", len(res))
    if res[:5]:
        print(res[:5])
