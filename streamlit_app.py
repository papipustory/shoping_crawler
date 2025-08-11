# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from danawa import DanawaParser

st.set_page_config(
    page_title="다나와 가격비교",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------------
# 세션 상태
# --------------------------------
if "options" not in st.session_state:
    st.session_state.options = []  # [{'category':'제조사','name':'Samsung','code':'702'}, ...]
if "name_to_code" not in st.session_state:
    st.session_state.name_to_code = {}  # {'Samsung':'702', ...}
if "last_keyword" not in st.session_state:
    st.session_state.last_keyword = ""
if "selected_names" not in st.session_state:
    st.session_state.selected_names = []
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()

parser = DanawaParser()

st.markdown("## 🛒 다나와 가격비교 검색")
st.caption("키워드를 입력하고, '검색 옵션 로드' → 제조사 선택 → '제품 검색하기' 순서로 진행하세요.")

# --------------------------------
# 검색 키워드 입력
# --------------------------------
col_kw, col_btn = st.columns([3, 1])
with col_kw:
    keyword = st.text_input("검색어 입력", placeholder="찾고자 하는 제품명 입력 (예: ssd 9a1)")
with col_btn:
    if st.button("검색 옵션 로드", use_container_width=True, type="primary"):
        if not keyword.strip():
            st.warning("검색어를 입력해주세요.")
        else:
            st.session_state.last_keyword = keyword.strip()
            with st.spinner("옵션 로딩 중..."):
                options = parser.get_search_options(st.session_state.last_keyword)
                # 비숫자 코드 제거는 danawa.py에서 이미 처리하지만 안전차원에서 한 번 더
                options = [o for o in options if str(o.get("code", "")).isdigit() and o.get("name")]
                st.session_state.options = options
                st.session_state.name_to_code = {o["name"].strip(): o["code"].strip() for o in options}
            if not options:
                st.error("검색 옵션을 찾지 못했습니다. (기본 매핑도 비어 있음)")
            else:
                st.success(f"옵션 {len(options)}개 로드 완료.")

# --------------------------------
# 제조사 선택 (체크박스/멀티선택)
# --------------------------------
st.markdown("### 제조사 선택")
if not st.session_state.options:
    st.info("먼저 상단의 '검색 옵션 로드' 버튼을 눌러 옵션을 가져오세요.")
else:
    # 이름 리스트
    names = [o["name"] for o in st.session_state.options]
    # 기존 선택 유지
    st.session_state.selected_names = st.multiselect(
        "원하는 제조사를 선택하세요",
        options=names,
        default=st.session_state.selected_names,
        help="제조사를 다중 선택할 수 있습니다.",
    )

# --------------------------------
# 제품 검색
# --------------------------------
st.markdown("### 제품 검색")
search_col1, search_col2 = st.columns([1, 3])
with search_col1:
    clicked_search = st.button("제품 검색하기", type="primary", use_container_width=True)
with search_col2:
    st.caption("선택한 제조사 코드로 검색합니다. (maker=코드1,코드2,...)")

if clicked_search:
    if not st.session_state.last_keyword.strip():
        st.warning("먼저 '검색 옵션 로드'로 옵션을 불러오세요.")
    else:
        # 선택된 이름 → 숫자 코드로 변환
        codes = []
        for nm in st.session_state.selected_names:
            code = st.session_state.name_to_code.get(nm.strip())
            if code and code.isdigit():
                codes.append(code)
        codes = list(dict.fromkeys(codes))  # 중복 제거

        with st.spinner("검색 중..."):
            results = parser.search_products(st.session_state.last_keyword, codes if codes else None)
            df = parser.to_dataframe(results)
            st.session_state.df = df

        st.success(f"검색 완료. 결과 {len(st.session_state.df)}개")
        if st.session_state.df.empty:
            st.info("표시할 결과가 없습니다. 제조사 선택을 바꾸거나 키워드를 조정해 보세요.")

# --------------------------------
# 결과 표시 + 엑셀 다운로드
# --------------------------------
st.markdown("### 결과 확인")
if st.session_state.df is not None and not st.session_state.df.empty:
    st.dataframe(
        st.session_state.df,
        use_container_width=True,
        hide_index=True,
    )

    # 엑셀 다운로드
    xbytes = parser.to_excel_bytes(st.session_state.df)
    st.download_button(
        label="Excel 다운로드",
        data=xbytes,
        file_name=f"danawa_{st.session_state.last_keyword}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.info("검색 결과 테이블이 여기에 표시됩니다.")

# --------------------------------
# 푸터
# --------------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center; opacity:0.8'>Made with ❤️ using Streamlit</div>",
    unsafe_allow_html=True,
)
