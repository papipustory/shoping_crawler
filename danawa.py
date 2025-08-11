# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
import time
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
        "X-Requested-With": "XMLHttpRequest"
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
    def _build_params(self, keyword: str, maker_codes_csv: Optional[str], sort_type: str = "saveDESC") -> Dict:
        # keyword와 k1 둘 다 넣어 호환성 확보
        params = {
            "keyword": keyword,
            "originalQuery": keyword,
            "keywordType": "1",
            "sort": sort_type,
            "volumeType": "allvs",
            "page": "1",
            "limit": "40",
            "boost": "true"
        }
        if maker_codes_csv:
            # 일부 페이지는 maker, 일부는 brand로 동작 → 둘 다 넣어 안전빵
            params["maker"] = maker_codes_csv
            params["brand"] = maker_codes_csv
        return params

    def _parse_product_page(self, soup: BeautifulSoup) -> Dict:
        """제품 상세 페이지의 BeautifulSoup 객체에서 가격과 스펙을 파싱합니다."""
        details = {"가격": "", "가격(원문)": "", "스펙": ""}
        
        # 가격 파싱
        price_el = soup.select_one("em.text__num")
        if price_el:
            price_text = price_el.get_text(strip=True)
            details["가격(원문)"] = price_text
            details["가격"] = self._to_int_price(price_text)

        # 스펙 파싱
        spec_table = soup.find("table", class_="spec_tbl")
        if spec_table:
            specs = []
            for row in spec_table.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    spec_key = th.get_text(" ", strip=True)
                    spec_value = td.get_text(" ", strip=True)
                    specs.append(f"{spec_key}: {spec_value}")
            details["스펙"] = " / ".join(specs)
            
        return details

    def _get_product_details(self, product_url: str) -> Dict:
        """제품 상세 페이지 URL을 방문하여 가격과 스펙을 가져옵니다."""
        if not product_url.startswith("http"):
            product_url = "https:" + product_url

        print(f"[상세] {product_url} 페이지에서 정보 수집 중...")
        resp = self._get(product_url)
        if not resp:
            return {}
        
        time.sleep(self.delay)
        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_product_page(soup)

    def search_products(self, keyword: str, maker_codes: Optional[List[str]] = None, sort_type: str = "saveDESC", limit: int = 5) -> List[Dict]:
        maker_csv = None
        if maker_codes:
            codes = [str(c).strip() for c in maker_codes if str(c).strip()]
            maker_csv = ",".join(codes) if codes else None

        params = self._build_params(keyword, maker_csv, sort_type)
        print(f"[검색] 요청 URL: {self.BASE_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")
        
        resp = self._get(self.BASE_URL, params=params)
        if not resp:
            return []

        self.last_html = resp.text
        soup = BeautifulSoup(resp.text, "lxml")

        # JSON-LD 데이터 우선 파싱
        results = []
        json_ld_script = soup.find("script", {"type": "application/ld+json"})
        if json_ld_script:
            try:
                json_text = json_ld_script.string or ""
                if json_text.strip():
                    data = json.loads(json_text)
                    if data and "itemListElement" in data:
                        items = data["itemListElement"]
                        
                        # 제조사 필터링 (클라이언트 사이드)
                        if maker_codes:
                            # get_search_options는 HTTP 요청을 다시 보내므로, 여기서는 제품명으로만 필터링
                            # 더 정확한 방법은 제조사 코드와 이름을 미리 매핑해두는 것
                            # 지금은 간단하게 제품명에 제조사 이름이 포함되는지 체크
                            opts = self.get_search_options(keyword)
                            code_to_name = {opt['code']: opt['name'] for opt in opts}
                            maker_names = [code_to_name.get(code, "").upper() for code in maker_codes if code in code_to_name]
                            
                            if maker_names:
                                filtered_items = []
                                for item in items:
                                    item_name = item.get("name", "").upper()
                                    if any(maker_name in item_name for maker_name in maker_names):
                                        filtered_items.append(item)
                                items = filtered_items

                        for item in items[:limit]:
                            product_info = {
                                "제품명": item.get("name", ""),
                                "URL": item.get("url", ""),
                                "가격": "",
                                "가격(원문)": "정보 없음",
                                "스펙": ""
                            }
                            if product_info["URL"]:
                                details = self._get_product_details(product_info["URL"])
                                product_info.update(details)
                            
                            results.append(product_info)

                        print(f"[성공] JSON-LD에서 {len(results)}개 제품 처리 완료.")
                        return results
            except (json.JSONDecodeError, TypeError) as e:
                print(f"[오류] JSON-LD 파싱 실패: {e}")

        print("[경고] JSON-LD 파싱에 실패하여 제품 정보를 가져올 수 없습니다.")
        return []

    def search_products_with_sorting(self, keyword: str, maker_codes: Optional[List[str]] = None, limit: int = 5) -> Dict:
        """
        인기순과 상품평순으로 각각 검색해서 지정된 개수만큼 결과를 반환
        """
        results = {}
        
        if maker_codes:
            print(f"[필터] 적용할 제조사 코드: {', '.join(maker_codes)}")

        print(f"\n--- 인기순 (saveDESC) 검색 ---")
        popular_results = self.search_products(keyword, maker_codes, "saveDESC", limit)
        results["인기순"] = popular_results
        
        print(f"\n--- 상품평 많은순 (opinionDESC) 검색 ---")
        review_results = self.search_products(keyword, maker_codes, "opinionDESC", limit)
        results["상품평순"] = review_results
        
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
    parser = argparse.ArgumentParser(description="다나와 상품 정보를 크롤링합니다.")
    parser.add_argument("--keyword", type=str, required=True, help="검색할 키워드")
    parser.add_argument("--maker", type=str, default="", help="제조사 코드 (쉼표로 구분)")
    parser.add_argument("--limit", type=int, default=5, help="각 정렬별로 가져올 결과 개수")
    args = parser.parse_args()

    dn = DanawaParser()
    
    # 제조사 코드 파싱
    makers = [m.strip() for m in args.maker.split(",") if m.strip()] if args.maker else []
    
    # 인기순/상품평순 검색
    print(f"\n=== '{args.keyword}' 제품 검색 시작 (각 {args.limit}개) ===")
    results = dn.search_products_with_sorting(args.keyword, makers if makers else None, args.limit)
    
    for sort_type, products in results.items():
        print(f"\n--- {sort_type} ({len(products)}개) ---")
        if not products:
            print("결과 없음")
            continue
        for i, product in enumerate(products, 1):
            print(f"{i}. {product.get('제품명', 'N/A')}")
            print(f"   가격: {product.get('가격(원문)', 'N/A')}")
            # 스펙이 길 수 있으므로 일부만 표시
            spec_summary = product.get('스펙', 'N/A')
            if len(spec_summary) > 150:
                spec_summary = spec_summary[:150] + "..."
            print(f"   스펙: {spec_summary}")
            print()
