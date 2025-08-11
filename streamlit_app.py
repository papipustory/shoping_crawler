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
if "selected_map" not in st.session_state:
    st.session_state.selected_map = {}  # {'Samsung': True/False, ...}
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "filter_text" not in st.session_state:
    st.session_state.filter_text = ""

parser = DanawaParser()

st.markdown("## 🛒 다나와 가격비교 검색")
st.caption("키워드를 입력하고, '검색 옵션 로드' → 제조사 선택(체크박스) → '제품 검색하기' 순서로 진행하세요.")

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
                # 페이지가 제공한 옵션만 사용(비숫자/공백 제거는 danawa.py에서 처리)
                options = [
                    {"name": o["name"].strip(), "code": o["code"].strip(), "category": o.get("category", "제조사")}
                    for o in options
                    if o.get("name") and str(o.get("code", "")).isdigit()
                ]
                st.session_state.options = options
                st.session_state.name_to_code = {o["name"]: o["code"] for o in options}

                # 체크박스 상태 초기화 (옵션 목록 기준으로 리셋)
                st.session_state.selected_map = {o["name"]: False for o in options}
                st.session_state.filter_text = ""

            if not options:
                st.info("이 키워드에는 선택 가능한 '제조사/브랜드' 옵션이 페이지에 노출되지 않았습니다.")
            else:
                st.success(f"옵션 {len(options)}개 로드 완료.")

            # 디버그 정보 섹션
            dbg = parser.get_debug_dump()
            with st.expander("🔎 디버그 정보 보기", expanded=False):
                st.write("요청 URL:", (dbg["request_url"] or b"").decode("utf-8"))
                st.write("찾은 옵션 수:", len(options))
                if options:
                    st.write("옵션 미리보기:", [f'{o["name"]}({o["code"]})' for o in options[:12]])
                c1, c2 = st.columns(2)
                with c1:
                    if dbg["page_html"]:
                        st.download_button(
                            label="페이지 원본 HTML 다운로드",
                            data=dbg["page_html"],
                            file_name=f"danawa_page_{st.session_state.last_keyword}.html",
                            mime="text/html",
                            use_container_width=True,
                        )
                with c2:
                    if dbg["option_block_html"]:
                        st.download_button(
                            label="옵션 블록 HTML 다운로드",
                            data=dbg["option_block_html"],
                            file_name=f"danawa_option_{st.session_state.last_keyword}.html",
                            mime="text/html",
                            use_container_width=True,
                        )

# --------------------------------
# 제조사 선택 (체크박스 UI)
# --------------------------------
st.markdown("### 제조사 선택")

if not st.session_state.options:
    st.info("먼저 상단의 '검색 옵션 로드' 버튼을 눌러 옵션을 가져오세요.")
else:
    # 필터 입력(이름 검색)
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        st.session_state.filter_text = st.text_input(
            "제조사 검색(필터)", value=st.session_state.filter_text, placeholder="예: sam, king, wd ..."
        )
    with fc2:
        if st.button("전체 선택", use_container_width=True):
            ft = st.session_state.filter_text.strip().lower()
            for name in st.session_state.selected_map.keys():
                if not ft or ft in name.lower():
                    st.session_state.selected_map[name] = True
    with fc3:
        if st.button("전체 해제", use_container_width=True):
            ft = st.session_state.filter_text.strip().lower()
            for name in st.session_state.selected_map.keys():
                if not ft or ft in name.lower():
                    st.session_state.selected_map[name] = False

    # 필터 적용 목록
    filter_text = st.session_state.filter_text.strip().lower()
    visible_names = [
        o["name"] for o in st.session_state.options
        if (not filter_text or filter_text in o["name"].lower())
    ]

    # 3열 그리드로 체크박스 배치
    cols = st.columns(3)
    for idx, name in enumerate(visible_names):
        col = cols[idx % 3]
        with col:
            current = st.session_state.selected_map.get(name, False)
            new_val = st.checkbox(name, value=current, key=f"cb_{name}")
            st.session_state.selected_map[name] = new_val

# --------------------------------
# 제품 검색
# --------------------------------
st.markdown("### 제품 검색")
search_col1, search_col2 = st.columns([1, 3])
with search_col1:
    clicked_search = st.button("제품 검색하기", type="primary", use_container_width=True)
with search_col2:
    st.caption("체크한 제조사의 **숫자 코드**만 maker 파라미터에 전달됩니다. (maker=코드1,코드2,...)")

if clicked_search:
    if not st.session_state.last_keyword.strip():
        st.warning("먼저 '검색 옵션 로드'로 옵션을 불러오세요.")
    else:
        # 체크된 이름 → 숫자 코드로 변환
        selected_names = [n for n, v in st.session_state.selected_map.items() if v]
        codes = []
        for nm in selected_names:
            code = st.session_state.name_to_code.get(nm)
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
