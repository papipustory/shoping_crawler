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
    - 키워드 페이지에서 '제조사/브랜드' 옵션 추출
      · 체크박스/버튼/링크 모두 지원, 숫자 아닌 코드(예: '삼성전자')도 허용
    - maker/brand 파라미터로 필터 검색
    - 제품명/가격/스펙 파싱 (goods-list 구조)
    - 디버그: 요청 URL/페이지 HTML/옵션 블록 HTML 저장
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

    # 제품 파싱 셀렉터 (goods-list 구조)
    SELECTORS = {
        "items_strict": 'ul#productListArea_list > li.goods-list__item[data-itemtype="standard"]',
        "items_loose": [
            "li.goods-list__item[data-itemtype='standard']",
            "li.goods-list__item",
            "div.goods-list__item",
        ],
        "name": "span.goods-list__title",
        "price": "div.goods-list__price em.number",
        "spec_simple": "div.spec-box__inner[data-desctype='simple']",
        "spec_detail": "div.spec-box__inner[data-desctype='detail']",
    }

    def __init__(self, delay: float = 0.6):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.delay = delay
        self.last_request_url: Optional[str] = None
        self.last_html: Optional[str] = None
        self.last_option_html: Optional[str] = None

    # ---------------- HTTP ----------------
    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        try:
            resp = self.session.get(url, params=params, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            self.last_request_url = resp.url
            return resp
        except requests.RequestException as e:
            print(f"[HTTP ERROR] GET {url} params={params} -> {e}")
            return None

    # ------------- 옵션 추출 -------------
    def get_search_options(self, keyword: str) -> List[Dict]:
        """페이지에 노출된 제조사/브랜드 수집 (숫자/문자 코드 모두 허용)."""
        resp = self._get(self.BASE_URL, params={"k1": keyword, "keyword": keyword})
        if not resp:
            self.last_html = None
            self.last_option_html = None
            return []

        self.last_html = resp.text
        soup = BeautifulSoup(resp.text, "lxml")

        # 1) maker 관련 탭/컨테이너
        options = self._extract_from_known_tabs(soup)
        if options:
            return options

        # 2) 제목(제조사/브랜드) 근처 블록
        options = self._extract_from_heading_blocks(soup)
        if options:
            return options

        # 3) maker 파라미터가 걸린 링크에서 추출 (예외 케이스)
        options = self._extract_from_links_with_maker(soup)
        return options

    def _collect_options_from_container(self, container, out: List[Dict]):
        if not container:
            return
        # button[data-optioncode]
        for b in container.select("button"):
            name = (b.get("data-optionname") or b.get_text(strip=True) or "").strip()
            code = (b.get("data-optioncode") or b.get("data-value") or b.get("value") or "").strip()
            # 숫자 강제하지 않음 — 그대로 사용 (예: '삼성전자')
            if code and name:
                out.append({"category": "제조사", "name": name, "code": code})

        # input[type=checkbox] + label
        for inp in container.select('input[type="checkbox"]'):
            code = (inp.get("value") or "").strip()
            if not code:
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
            if name and code:
                out.append({"category": "제조사", "name": name, "code": code})

    def _extract_from_known_tabs(self, soup: BeautifulSoup) -> List[Dict]:
        options: List[Dict] = []
        known_ids = ["makerBrandTab", "makerOptionTab", "makerTab", "brandTab"]
        for kid in known_ids:
            cont = soup.find(id=kid)
            self._collect_options_from_container(cont, options)
            if options:
                self.last_option_html = str(cont) if cont else ""
                break

        if not options:
            # class에 maker/brand 포함된 컨테이너도 탐색
            conts = []
            for div in soup.find_all(True, {"class": True}):
                classes = " ".join(div.get("class", [])).lower()
                if "maker" in classes or "brand" in classes:
                    conts.append(div)
            for c in conts[:3]:
                self._collect_options_from_container(c, options)
                if options:
                    self.last_option_html = str(c)
                    break

        # 정리(코드+이름 기준 중복 제거)
        uniq = {}
        for o in options:
            key = (o["code"], o["name"])
            if o["code"] and o["name"] and key not in uniq:
                uniq[key] = {"category": "제조사", "name": o["name"], "code": o["code"]}
        return list(uniq.values())

    def _extract_from_heading_blocks(self, soup: BeautifulSoup) -> List[Dict]:
        options: List[Dict] = []
        title_re = re.compile(r"(제조사\s*\/\s*브랜드|제조사|브랜드)")
        title_nodes = [t for t in soup.find_all(string=title_re)]

        for t in title_nodes:
            el = t.parent
            if not el:
                continue
            candidates = [
                el,
                el.parent if el else None,
                el.find_next_sibling() if el else None,
                el.parent.find_next_sibling() if el and el.parent else None,
            ]
            for cand in [c for c in candidates if c]:
                self._collect_options_from_container(cand, options)
                if options:
                    self.last_option_html = str(cand)
                    break
            if options:
                break

        uniq = {}
        for o in options:
            key = (o["code"], o["name"])
            if o["code"] and o["name"] and key not in uniq:
                uniq[key] = {"category": "제조사", "name": o["name"], "code": o["code"]}
        return list(uniq.values())

    def _extract_from_links_with_maker(self, soup: BeautifulSoup) -> List[Dict]:
        options: List[Dict] = []
        for a in soup.select('a[href*="maker="]'):
            href = a.get("href", "")
            m = re.search(r"[?&]maker=([^&#]+)", href)
            if not m:
                continue
            code = m.group(1)
            name = a.get_text(strip=True) or "제조사"
            if code:
                options.append({"category": "제조사", "name": name, "code": code})
        # 중복 제거
        uniq = {}
        for o in options:
            key = (o["code"], o["name"])
            if key not in uniq:
                uniq[key] = o
        return list(uniq.values())

    # ---------------- 제품 검색 ----------------
    def _build_params(self, keyword: str, maker_codes_csv: Optional[str]) -> Dict:
        # keyword와 k1 둘 다 넣어 호환성 확보
        params = {"k1": keyword, "keyword": keyword}
        if maker_codes_csv:
            # 일부 페이지는 maker, 일부는 brand로 동작 → 둘 다 넣어 안전빵
            params["maker"] = maker_codes_csv
            params["brand"] = maker_codes_csv
        return params

    def search_products(self, keyword: str, maker_codes: Optional[List[str]] = None) -> List[Dict]:
        maker_csv = None
        if maker_codes:
            # 숫자 강제하지 않음. 그대로 쉼표 연결(예: '702,4213' or '삼성전자')
            codes = [str(c).strip() for c in maker_codes if str(c).strip()]
            maker_csv = ",".join(codes) if codes else None

        resp = self._get(self.BASE_URL, params=self._build_params(keyword, maker_csv))
        if not resp:
            return []

        self.last_html = resp.text
        soup = BeautifulSoup(resp.text, "lxml")

        # 1) 엄격 셀렉터
        item_nodes = soup.select(self.SELECTORS["items_strict"])
        # 2) 없으면 루즈 셀렉터들 시도
        if not item_nodes:
            for css in self.SELECTORS["items_loose"]:
                item_nodes = soup.select(css)
                if item_nodes:
                    break

        results = []
        for node in item_nodes:
            # 광고/비표준 항목 제외
            itemtype = node.get("data-itemtype", "")
            if itemtype and itemtype != "standard":
                continue

            # 제품명
            name_el = node.select_one(self.SELECTORS["name"])
            name = name_el.get_text(strip=True) if name_el else ""

            # 가격
            price_el = node.select_one(self.SELECTORS["price"])
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = self._to_int_price(price_text)

            # 스펙: simple 우선, 없으면 detail
            spec_el = node.select_one(self.SELECTORS["spec_simple"]) or node.select_one(self.SELECTORS["spec_detail"])
            spec_text = ""
            if spec_el:
                spans = [s.get_text(" ", strip=True) for s in spec_el.select("span") if s.get_text(strip=True)]
                if not spans:
                    spec_text = spec_el.get_text(" ", strip=True)
                else:
                    # 중간 구분자(span.slash)는 제거하고 값만 '/'로 합침
                    spec_text = " / ".join([s for s in spans if s != "/"])

            if not (name or price_text or spec_text):
                continue

            results.append({
                "제품명": name,
                "가격": price if price is not None else "",
                "가격(원문)": price_text,
                "스펙": spec_text
            })

        return results

    # ---------------- 유틸 ----------------
    @staticmethod
    def _to_int_price(text: str) -> Optional[int]:
        if not text:
            return None
        digits = re.findall(r"\d+", text.replace(",", ""))
        if not digits:
            return None
        try:
            return int("".join(digits))
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
    print("[옵션수]", len(opts), opts[:10])

    makers = [m.strip() for m in args.maker.split(",") if m.strip()] if args.maker else []
    res = dn.search_products(args.keyword, makers if makers else None)
    print("[결과수]", len(res))
    for r in res[:5]:
        print(r)
