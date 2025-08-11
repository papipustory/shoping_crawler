import streamlit as st
import pandas as pd
from io import BytesIO
from danawa import DanawaParser
from guidecom import GuidecomParser
import time
import re

# --- 페이지 설정 ---
st.set_page_config(
    page_title="가격 비교 사이트",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS 스타일 ---
st.markdown("""
<style>
    /* ... (기존 CSS와 동일) ... */
    .main { padding: 0rem 1rem; }
    .stApp { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    .main-header { background: linear-gradient(135deg, #2c3e50, #3498db); padding: 2rem; border-radius: 15px; margin-bottom: 2rem; text-align: center; color: white; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
    .search-container { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); margin-bottom: 2rem; }
    .manufacturer-grid { background: #f8f9fa; padding: 1.5rem; border-radius: 10px; border: 1px solid #dee2e6; }
    .results-container { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    .metric-container { background: linear-gradient(135deg, #27ae60, #2ecc71); padding: 0.8rem; border-radius: 8px; color: white; text-align: center; margin: 0.3rem; font-size: 0.9rem; }
    .metric-container h2 { font-size: 1.5rem; margin-bottom: 0.2rem; }
    .metric-container p { font-size: 0.8rem; margin-bottom: 0; }
    .stRadio > div { flex-direction: row; }
    .stButton > button { background: linear-gradient(135deg, #3498db, #2980b9); color: white; border: none; border-radius: 8px; padding: 0.75rem 2rem; font-weight: 600; box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3); transition: all 0.3s ease; }
    .stButton > button:hover { box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4); transform: translateY(-2px); }
</style>
""", unsafe_allow_html=True)


# --- 세션 상태 관리 ---
def init_session_state():
    if 'site' not in st.session_state:
        st.session_state.site = '다나와'
    if 'parser' not in st.session_state:
        st.session_state.parser = DanawaParser()
    if 'search_options' not in st.session_state:
        st.session_state.search_options = []
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    if 'show_manufacturers' not in st.session_state:
        st.session_state.show_manufacturers = False
    if 'search_keyword' not in st.session_state:
        st.session_state.search_keyword = ""

init_session_state()

# --- 공통 함수 ---
def extract_price_number(price_str):
    numbers = re.findall(r'[0-9,]+', price_str)
    return int(numbers[0].replace(',', '')) if numbers else 999999999

def run_search(parser, keyword, option_filter=None):
    all_products = []
    if isinstance(parser, DanawaParser):
        results = parser.search_all_categories(keyword, option_filter)
        for prods in results.values():
            all_products.extend(prods)
    elif isinstance(parser, GuidecomParser):
        results = parser.search_all_categories(keyword)
        for prods in results.values():
            all_products.extend(prods)

    seen_names = set()
    unique_products = []
    for product in all_products:
        if product.name not in seen_names:
            seen_names.add(product.name)
            unique_products.append(product)
    
    unique_products.sort(key=lambda p: extract_price_number(p.price))
    return unique_products

# --- UI 렌더링 ---

# 사이트 선택
site_choice = st.radio(
    "**검색할 사이트를 선택하세요**",
    ('다나와', '가이드컴'),
    horizontal=True,
    key='site_selector'
)

if site_choice != st.session_state.site:
    st.session_state.site = site_choice
    st.session_state.parser = DanawaParser() if site_choice == '다나와' else GuidecomParser()
    st.session_state.search_options = []
    st.session_state.search_results = []
    st.session_state.show_manufacturers = False
    st.session_state.search_keyword = ""
    st.rerun()

# 메인 헤더
st.markdown(f'''
<div class="main-header">
    <h1>🛒 {st.session_state.site} 가격비교</h1>
    <p>최저가 제품을 쉽고 빠르게 찾아보세요</p>
</div>
''', unsafe_allow_html=True)

# 검색 컨테이너
with st.container():
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    st.markdown("### 🔍 제품 검색")
    
    search_keyword = st.text_input(
        "검색할 제품명을 입력하세요",
        placeholder="예: 9a1, RTX 4090, 삼성 SSD...",
        key="search_input",
        value=st.session_state.search_keyword
    )
    st.session_state.search_keyword = search_keyword

    # --- 다나와 UI ---
    if st.session_state.site == '다나와':
        if st.button("🔍 제조사 옵션 로드", key="load_options"):
            if search_keyword.strip():
                with st.spinner('제조사 옵션을 가져오는 중...'):
                    options = st.session_state.parser.get_search_options(search_keyword.strip())
                    st.session_state.search_options = [opt for opt in options if opt['category'] == '제조사']
                    st.session_state.show_manufacturers = True
                    if st.session_state.search_options:
                        st.success(f"✅ {len(st.session_state.search_options)}개의 제조사 옵션을 찾았습니다!")
                    else:
                        st.warning("⚠️ 제조사 옵션을 찾을 수 없습니다.")
            else:
                st.error("❌ 검색어를 입력해주세요.")

    # --- 가이드컴 UI ---
    else:
        if st.button("🛒 제품 검색하기", key="search_guidecom"):
            if search_keyword.strip():
                with st.spinner('제품을 검색하는 중...'):
                    st.session_state.search_results = run_search(st.session_state.parser, search_keyword.strip())
                    if st.session_state.search_results:
                        st.success(f"✅ {len(st.session_state.search_results)}개의 제품을 찾았습니다!")
                    else:
                        st.warning("⚠️ 검색 결과가 없습니다.")
            else:
                st.error("❌ 검색어를 입력해주세요.")
    
    st.markdown('</div>', unsafe_allow_html=True)

# 다나와 제조사 선택 및 검색
if st.session_state.site == '다나와' and st.session_state.show_manufacturers:
    st.markdown('<div class="manufacturer-grid" style="margin-bottom: 1rem;">', unsafe_allow_html=True)
    st.markdown("### 🏭 제조사 선택 (미선택 시 전체 검색)")
    
    manufacturers = st.session_state.search_options
    cols = st.columns(min(4, len(manufacturers)))
    selected_manufacturers = []
    for i, m in enumerate(manufacturers):
        with cols[i % len(cols)]:
            if st.checkbox(m['name'], key=f"m_{m['code']}"):
                selected_manufacturers.append(m['code'])
    
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🛒 제품 검색하기", key="search_danawa"):
        if search_keyword.strip():
            with st.spinner('제품을 검색하는 중...'):
                all_products = []
                if selected_manufacturers:
                    for code in selected_manufacturers:
                        products = run_search(st.session_state.parser, search_keyword.strip(), f"maker={code}")
                        all_products.extend(products)
                else:
                    all_products = run_search(st.session_state.parser, search_keyword.strip())
                
                st.session_state.search_results = all_products
                if st.session_state.search_results:
                    st.success(f"✅ {len(st.session_state.search_results)}개의 제품을 찾았습니다!")
                else:
                    st.warning("⚠️ 검색 결과가 없습니다.")
        else:
            st.error("❌ 검색어를 입력해주세요.")

# 검색 결과 표시
if st.session_state.search_results:
    with st.container():
        st.markdown('<div class="results-container">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.markdown(f'''<div class="metric-container"><h2>{len(st.session_state.search_results)}</h2><p>총 제품 수</p></div>''', unsafe_allow_html=True)
        with col2:
            st.markdown(f'''<div class="metric-container"><h2>{st.session_state.search_keyword}</h2><p>검색어</p></div>''', unsafe_allow_html=True)
        
        # Excel 다운로드
        with col3:
            df = pd.DataFrame([{
                'No': i + 1,
                '제품명': p.name,
                '가격': p.price,
                '세부사양': p.specifications
            } for i, p in enumerate(st.session_state.search_results)])
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=f'{st.session_state.site} 검색결과', index=False)
                worksheet = writer.sheets[f'{st.session_state.site} 검색결과']
                # ... (엑셀 스타일링은 기존과 유사하게 적용 가능)
                column_widths = [8, 50, 15, 80]
                for i, width in enumerate(column_widths, 1):
                    worksheet.column_dimensions[worksheet.cell(1, i).column_letter].width = width
            
            st.download_button(
                label="📥 Excel 다운로드",
                data=output.getvalue(),
                file_name=f"{st.session_state.search_keyword}_{st.session_state.site}_결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.markdown("---")
        st.markdown("### 📋 검색 결과")
        
        df_display = pd.DataFrame([{
            'No': i + 1, '제품명': p.name, '가격': p.price, '세부사양': p.specifications
        } for i, p in enumerate(st.session_state.search_results)])
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn("No", width=60),
                "제품명": st.column_config.TextColumn("제품명", width=350),
                "가격": st.column_config.TextColumn("가격", width=120),
                "세부사양": st.column_config.TextColumn("세부사양")
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)

# 푸터
st.markdown("---")
st.markdown(f'''
<div style='text-align: center; color: white; padding: 1rem;'>
    <p>🛒 {st.session_state.site} 가격비교 웹앱 | Made with ❤️ using Streamlit</p>
</div>
''', unsafe_allow_html=True)
