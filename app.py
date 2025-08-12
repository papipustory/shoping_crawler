import streamlit as st
import pandas as pd
from danawa import DanawaParser, Product

st.set_page_config(page_title="다나와 상품 검색", layout="wide")

st.title("🛒 다나와 상품 검색기")

# Initialize session state
if 'parser' not in st.session_state:
    st.session_state.parser = DanawaParser()
if 'keyword' not in st.session_state:
    st.session_state.keyword = ""
if 'manufacturers' not in st.session_state:
    st.session_state.manufacturers = []
if 'selected_manufacturers' not in st.session_state:
    st.session_state.selected_manufacturers = {}
if 'products' not in st.session_state:
    st.session_state.products = []

# --- 1. Keyword Input using a Form ---
with st.form(key="search_form"):
    keyword_input = st.text_input(
        "검색어를 입력하세요:", 
        placeholder="예: 그래픽카드, SSD", 
        value=st.session_state.get("keyword", "")
    )
    search_button = st.form_submit_button(label="제조사 검색")

if search_button:
    st.session_state.keyword = keyword_input
    st.session_state.products = [] # 새로운 검색 시 이전 제품 결과 초기화
    if st.session_state.keyword:
        with st.spinner("제조사 정보를 가져오는 중..."):
            st.session_state.manufacturers = st.session_state.parser.get_search_options(st.session_state.keyword)
            st.session_state.selected_manufacturers = {m['name']: False for m in st.session_state.manufacturers}
            if not st.session_state.manufacturers:
                st.warning("해당 검색어에 대한 제조사 정보를 찾을 수 없습니다.")
    else:
        st.warning("검색어를 입력해주세요.")

# --- 2. Manufacturer Selection ---
if st.session_state.manufacturers:
    st.subheader("제조사를 선택하세요 (중복 가능)")
    with st.form(key="manufacturer_form"):
        cols = st.columns(4)
        selected_options = {}
        for i, manufacturer in enumerate(st.session_state.manufacturers):
            with cols[i % 4]:
                selected_options[manufacturer['name']] = st.checkbox(
                    manufacturer['name'],
                    key=f"chk_{manufacturer['code']}_{i}"
                )
        
        product_search_button = st.form_submit_button("선택한 제조사로 제품 검색")

    if product_search_button:
        selected_codes = [
            m['code'] for m in st.session_state.manufacturers 
            if selected_options.get(m['name'])
        ]
        
        if not selected_codes:
            st.warning("하나 이상의 제조사를 선택해주세요.")
        else:
            with st.spinner('제품 정보를 검색 중입니다...'):
                st.session_state.products = st.session_state.parser.get_unique_products(
                    st.session_state.keyword, selected_codes
                )
                if not st.session_state.products:
                    st.info("선택된 제조사의 제품을 찾을 수 없습니다.")

# --- 3. Display Results ---
if st.session_state.products:
    st.subheader(f"'{st.session_state.keyword}'에 대한 검색 결과")
    
    data = [{
        "제품명": p.name,
        "가격": p.price,
        "주요 사양": p.specifications
    } for p in st.session_state.products]
    
    df = pd.DataFrame(data)
    st.dataframe(df, height=35 * (len(df) + 1), use_container_width=True)

    # Reset button
    if st.button("새로 검색하기"):
        st.session_state.keyword = ""
        st.session_state.manufacturers = []
        st.session_state.selected_manufacturers = {}
        st.session_state.products = []
        st.rerun()
