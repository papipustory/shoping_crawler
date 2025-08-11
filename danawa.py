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

    # 제품 파싱 셀렉터 (새 구조 반영)
    SELECTORS = {
        "items_strict": 'ul#productListArea_list > li.goods-list__item[data-itemtype="standard"]',
        "items_loose": [
            "li.goods-list__item[data-itemtype='standard']",
            "li.goods-list__item",
            "div.goods-list__item",
        ],
        "name": "span.goods-list__title",
        "price": "div.goods-list__price em.number",
        # 간단/상세 스펙 모두 대응. 보이는 쪽(data-desctype='simple') 우선
        "spec_simple": "div.spec-box__inner[data-desctype='simple']",
        "spec_detail": "div.spec-box__inner[data-desctype='detail']",
    }

    def __init__(self, delay: float = 0.6):
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
            self.last_request_url = resp.url  # 최종 URL 저장
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

        # 1) maker 관련 탭에서 직접 추출
        options = self._extract_from_known_tabs(soup)
        if options:
            return options

        # 2) 제목 텍스트(제조사/브랜드 등) 근처에서 추출
        options = self._extract_from_heading_blocks(soup)
        return options

    def _collect_options_from_container(self, container, out: List[Dict]):
        if not container:
            return
        # button[data-optioncode]
        for b in container.select("button"):
            name = (b.get("data-optionname") or b.get_text(strip=True) or "").strip()
            code = (
                b.get("data-optioncode")
                or b.get("data-value")
                or b.get("value")
                or ""
            ).strip()
            if code.isdigit() and name:
                out.append({"category": "제조사", "name": name, "code": code})

        # input[type=checkbox] + label
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

        # 정리(코드 기준 중복 제거)
        uniq = {}
        for o in options:
            if o["code"].isdigit() and o["name"]:
                uniq[o["code"]] = {"category": "제조사", "name": o["name"], "code": o["code"]}
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
            if o["code"].isdigit() and o["name"]:
                uniq[o["code"]] = {"category": "제조사", "name": o["name"], "code": o["code"]}
        return list(uniq.values())

    # -----------------------------
    # 제품 검색 (goods-list 기반)
    # -----------------------------
    def _build_params(self, keyword: str, maker_codes_csv: Optional[str]) -> Dict:
        params = {"k1": keyword}
        if maker_codes_csv:
            params["maker"] = maker_codes_csv  # 쉼표 그대로 → requests가 인코딩
        return params

    def search_products(self, keyword: str, maker_codes: Optional[List[str]] = None) -> List[Dict]:
        maker_csv = None
        if maker_codes:
            codes = [c for c in maker_codes if str(c).isdigit()]
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
                    # 자식 span이 없으면 통째로 텍스트
                    spec_text = spec_el.get_text(" ", strip=True)
                else:
                    # 중간에 들어가는 슬래시는 UI용이니, 값만 '/'로 재구성
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

    # -----------------------------
    # 유틸
    # -----------------------------
    @staticmethod
    def _to_int_price(text: str) -> Optional[int]:
        if not text:
            return None
        # "1,939,210" → 1939210
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
    print("[옵션수]", len(opts))
    print(opts[:10])

    makers = [m.strip() for m in args.maker.split(",") if m.strip().isdigit()] if args.maker else []
    res = dn.search_products(args.keyword, makers if makers else None)
    print("[결과수]", len(res))
    for r in res[:5]:
        print(r)
