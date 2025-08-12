import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Product:
    name: str
    price: str
    specifications: str

class DanawaParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "https://search.danawa.com/dsearch.php"

    def get_search_options(self, keyword: str) -> List[Dict[str, str]]:
        params = {'query': keyword}
        try:
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            options = []

            option_area = soup.find('div', id='searchOptionListArea')
            if not option_area:
                return []

            maker_items = option_area.find_all('div', class_='basic_cate_item')
            for item in maker_items:
                checkbox = item.find('input', type='checkbox')
                label = item.find('label')
                if checkbox and label:
                    name_span = label.find('span', class_='name')
                    if name_span:
                        options.append({
                            'name': name_span.text.strip(),
                            'code': checkbox.get('value')
                        })
            return options
        except Exception as e:
            print(f"An error occurred while fetching search options: {e}")
            return []

    def search_products(self, keyword: str, sort_type: str, maker_codes: List[str], limit: int = 5) -> List[Product]:
        params = {
            'query': keyword,
            'sort': sort_type,
            'maker': ",".join(maker_codes)
        }
        try:
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            products = []
            
            product_list = soup.find('ul', class_='product_list')
            if not product_list:
                return []

            items = product_list.find_all('li', class_='prod_item')
            for item in items[:limit]:
                product = self._parse_product_item(item)
                if product:
                    products.append(product)
            return products
        except Exception as e:
            print(f"An error occurred while searching for products: {e}")
            return []

    def _parse_product_item(self, item) -> Optional[Product]:
        try:
            prod_info = item.find('div', class_='prod_info')
            if not prod_info:
                return None

            prod_name_tag = prod_info.find('p', class_='prod_name')
            name = prod_name_tag.a.text.strip() if prod_name_tag and prod_name_tag.a else "정보 없음"

            price_sect = item.find('p', class_='price_sect')
            price = price_sect.a.strong.text.strip() if price_sect and price_sect.a and price_sect.a.strong else "가격 문의"

            spec_list = item.find('div', class_='spec_list')
            specs = []
            if spec_list:
                spec_items = spec_list.find_all('a', class_='view_spec')
                for spec_item in spec_items:
                    # "상세 스펙 보기" 텍스트를 제외하고 스펙 정보만 추출
                    spec_text = spec_item.text.strip()
                    if spec_text and "상세 스펙 보기" not in spec_text:
                        specs.append(spec_text)

            specifications = " / ".join(specs) if specs else "사양 정보 없음"

            return Product(name=name, price=price, specifications=specifications)
        except Exception as e:
            print(f"Error parsing product item: {e}")
            return None

    def get_unique_products(self, keyword: str, maker_codes: List[str]) -> List[Product]:
        recommended_products = self.search_products(keyword, "saveDESC", maker_codes, limit=5)
        top_rated_products = self.search_products(keyword, "opinionDESC", maker_codes, limit=5)

        all_products = recommended_products + top_rated_products
        
        unique_products = []
        seen_names = set()
        for product in all_products:
            if product.name not in seen_names:
                unique_products.append(product)
                seen_names.add(product.name)
        
        return unique_products
