import streamlit as st
import pandas as pd
from io import BytesIO
from danawa import DanawaParser
import time

# 페이지 설정
st.set_page_config(
    page_title="다나와 가격비교",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 스타일
st.markdown("""
<style>
    .main {
        padding: 0rem 1rem;
    }
    
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main-header {
        background: linear-gradient(135deg, #2c3e50, #3498db);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    .search-container {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    
    .manufacturer-grid {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #dee2e6;
    }
    
    .results-container {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .metric-container {
        background: linear-gradient(135deg, #27ae60, #2ecc71);
        padding: 0.8rem;
        border-radius: 8px;
        color: white;
        text-align: center;
        margin: 0.3rem;
        font-size: 0.9rem;
    }
    
    .metric-container h2 {
        font-size: 1.5rem;
        margin-bottom: 0.2rem;
    }
    
    .metric-container p {
        font-size: 0.8rem;
        margin-bottom: 0;
    }
    
    .stSelectbox > div > div {
        background-color: white;
        border-radius: 8px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4);
        transform: translateY(-2px);
    }
    
    .download-button {
        background: linear-gradient(135deg, #27ae60, #229954) !important;
    }
</style>
""", unsafe_allow_html=True)

# 메인 헤더
st.markdown("""
<div class="main-header">
    <h1>🛒 다나와 가격비교</h1>
    <p>최저가 제품을 쉽고 빠르게 찾아보세요</p>
</div>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'parser' not in st.session_state:
    st.session_state.parser = DanawaParser()
if 'search_options' not in st.session_state:
    st.session_state.search_options = []
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'show_manufacturers' not in st.session_state:
    st.session_state.show_manufacturers = False

# 검색 컨테이너
with st.container():
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    
    st.markdown("### 🔍 제품 검색")
    
    # 검색어 입력
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_keyword = st.text_input(
            "검색할 제품명을 입력하세요",
            placeholder="예: 9a1, RTX 4090, 삼성 SSD...",
            key="search_input"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔍 검색 옵션 로드", key="load_options"):
            if search_keyword.strip():
                with st.spinner('검색 옵션을 가져오는 중...'):
                    try:
                        options = st.session_state.parser.get_search_options(search_keyword.strip())
                        # 제조사 옵션만 필터링
                        manufacturer_options = [opt for opt in options if opt['category'] == '제조사']
                        st.session_state.search_options = manufacturer_options
                        st.session_state.show_manufacturers = True
                        
                        if manufacturer_options:
                            st.success(f"✅ {len(manufacturer_options)}개의 제조사 옵션을 찾았습니다!")
                        else:
                            st.warning("⚠️ 제조사 옵션을 찾을 수 없습니다.")
                    except Exception as e:
                        st.error(f"❌ 옵션 조회 중 오류: {str(e)}")
            else:
                st.error("❌ 검색어를 입력해주세요.")
    
    st.markdown('</div>', unsafe_allow_html=True)

# 제조사 선택 영역
if st.session_state.show_manufacturers and st.session_state.search_options:
    st.markdown("---")
    st.markdown("### 🏭 제조사 선택 (다중선택 가능)")
    
    st.markdown('<div class="manufacturer-grid">', unsafe_allow_html=True)
        
        # 제조사 체크박스들을 열로 배치
        manufacturers = st.session_state.search_options
        cols = st.columns(min(4, len(manufacturers)))
        
        selected_manufacturers = []
        for i, manufacturer in enumerate(manufacturers):
            with cols[i % len(cols)]:
                if st.checkbox(
                    manufacturer['name'], 
                    key=f"manufacturer_{manufacturer['code']}"
                ):
                    selected_manufacturers.append(manufacturer['code'])
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 검색 버튼들
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            if st.button("🛒 제품 검색하기", key="search_products"):
                if search_keyword.strip():
                    with st.spinner('제품을 검색하는 중...'):
                        try:
                            all_products = []
                            
                            # 선택된 제조사가 있으면 각각 검색
                            if selected_manufacturers:
                                for manufacturer_code in selected_manufacturers:
                                    option_filter = f"maker={manufacturer_code}"
                                    results = st.session_state.parser.search_all_categories(
                                        search_keyword.strip(), option_filter
                                    )
                                    for category, products in results.items():
                                        all_products.extend(products)
                            else:
                                # 제조사 필터 없이 전체 검색
                                results = st.session_state.parser.search_all_categories(search_keyword.strip())
                                for category, products in results.items():
                                    all_products.extend(products)
                            
                            # 중복 제거 및 가격순 정렬
                            seen_names = set()
                            unique_products = []
                            for product in all_products:
                                if product.name not in seen_names:
                                    seen_names.add(product.name)
                                    unique_products.append(product)
                            
                            # 가격순 정렬
                            def extract_price_number(price_str):
                                import re
                                numbers = re.findall(r'[0-9,]+', price_str)
                                if numbers:
                                    return int(numbers[0].replace(',', ''))
                                return 999999999
                            
                            unique_products.sort(key=lambda p: extract_price_number(p.price))
                            
                            st.session_state.search_results = unique_products
                            
                            if unique_products:
                                st.success(f"✅ {len(unique_products)}개의 제품을 찾았습니다!")
                            else:
                                st.warning("⚠️ 검색 결과가 없습니다.")
                                
                        except Exception as e:
                            st.error(f"❌ 검색 중 오류: {str(e)}")
                else:
                    st.error("❌ 검색어를 입력해주세요.")
        
        with col2:
            if st.button("🔄 선택 초기화", key="clear_selection"):
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# 검색 결과 표시
if st.session_state.search_results:
    with st.container():
        st.markdown('<div class="results-container">', unsafe_allow_html=True)
        
        # 통계 정보 - 크기 조정 (2:2:1 비율)
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            st.markdown(f"""
            <div class="metric-container">
                <h2>{len(st.session_state.search_results)}</h2>
                <p>총 제품 수</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-container">
                <h2>{search_keyword}</h2>
                <p>검색어</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Excel 다운로드 버튼
            def create_excel_file():
                # 데이터프레임 생성
                data = []
                for i, product in enumerate(st.session_state.search_results, 1):
                    data.append({
                        'No': i,
                        '제품명': product.name,
                        '가격': product.price,
                        '세부사양': product.specifications
                    })
                
                df = pd.DataFrame(data)
                
                # 메모리에서 Excel 파일 생성
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='다나와 검색결과', index=False)
                    
                    # 스타일 적용
                    workbook = writer.book
                    worksheet = writer.sheets['다나와 검색결과']
                    
                    # 헤더 스타일
                    from openpyxl.styles import Font, Alignment, PatternFill
                    header_font = Font(bold=True, color="FFFFFF")
                    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                    header_alignment = Alignment(horizontal='center', vertical='center')
                    
                    for col_num, cell in enumerate(worksheet[1], 1):
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = header_alignment
                    
                    # 열 너비 조정
                    column_widths = [8, 50, 15, 80]
                    for i, width in enumerate(column_widths, 1):
                        worksheet.column_dimensions[worksheet.cell(1, i).column_letter].width = width
                
                output.seek(0)
                return output.getvalue()
            
            if st.button("📥 Excel 다운로드", key="download_excel", help="검색 결과를 Excel 파일로 다운로드"):
                try:
                    excel_data = create_excel_file()
                    st.download_button(
                        label="💾 Excel 파일 다운로드",
                        data=excel_data,
                        file_name=f"{search_keyword}_다나와_검색결과.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"❌ Excel 파일 생성 중 오류: {str(e)}")
        
        st.markdown("---")
        
        # 결과 테이블
        st.markdown("### 📋 검색 결과")
        
        # 데이터프레임 생성 및 표시
        data = []
        for i, product in enumerate(st.session_state.search_results, 1):
            data.append({
                'No': i,
                '제품명': product.name,
                '가격': product.price,
                '세부사양': product.specifications
            })
        
        df = pd.DataFrame(data)
        
        # 스타일이 적용된 데이터프레임 표시
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "No": st.column_config.NumberColumn(
                    "No",
                    width=60,
                    format="%d"
                ),
                "제품명": st.column_config.TextColumn(
                    "제품명",
                    width=350
                ),
                "가격": st.column_config.TextColumn(
                    "가격",
                    width=120
                ),
                "세부사양": st.column_config.TextColumn(
                    "세부사양",
                    width=400
                )
            }
        )
        
        st.markdown('</div>', unsafe_allow_html=True)

# 푸터
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: white; padding: 1rem;'>
        <p>🛒 다나와 가격비교 웹앱 | Made with ❤️ using Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True
)
