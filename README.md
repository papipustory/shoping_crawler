# 🛒 다나와 가격비교 웹앱

다나와 사이트에서 제품 정보를 크롤링하여 최저가 제품을 찾아주는 웹 애플리케이션입니다.

## ✨ 주요 기능

- 🔍 **제품 검색**: 키워드로 다나와 제품 검색
- 🏭 **제조사 필터**: 다중 선택 가능한 제조사 필터링
- 💰 **가격순 정렬**: 최저가부터 자동 정렬
- 📊 **Excel 다운로드**: 검색 결과를 Excel 파일로 다운로드
- 📱 **반응형 디자인**: 모바일/태블릿/데스크톱 지원

## 🚀 Streamlit Cloud 배포

### 1. GitHub 저장소 생성
1. GitHub에 새 저장소 생성
2. 이 폴더의 모든 파일을 업로드

### 2. Streamlit Cloud 배포
1. [Streamlit Cloud](https://streamlit.io/cloud) 접속
2. GitHub 계정으로 로그인
3. "New app" 클릭
4. 저장소 선택 및 `streamlit_app.py` 지정
5. Deploy 클릭

## 📁 파일 구조

```
가격 비교 사이트/
├── streamlit_app.py      # Streamlit 웹앱 메인 파일
├── danawa.py            # 다나와 크롤링 모듈
├── requirements.txt     # 필요한 패키지 목록
├── README.md           # 프로젝트 설명
└── 기존 파일들...
```

## 🛠️ 로컬 실행

```bash
# 패키지 설치
pip install -r requirements.txt

# Streamlit 앱 실행
streamlit run streamlit_app.py
```

## 📋 사용 방법

1. **검색어 입력**: 찾고자 하는 제품명 입력
2. **옵션 로드**: "검색 옵션 로드" 버튼 클릭
3. **제조사 선택**: 원하는 제조사들을 체크박스로 선택
4. **제품 검색**: "제품 검색하기" 버튼 클릭
5. **결과 확인**: 테이블에서 결과 확인
6. **Excel 다운로드**: 필요시 Excel 파일로 다운로드

## 🎨 주요 특징

- **모던한 UI**: 그라데이션과 카드 디자인
- **실시간 검색**: 빠른 응답과 부드러운 UX
- **다중 필터링**: 여러 제조사 동시 선택
- **자동 중복 제거**: 동일 제품 자동 필터링
- **가격순 정렬**: 최저가부터 표시

## 🔧 기술 스택

- **Frontend**: Streamlit
- **Backend**: Python
- **크롤링**: BeautifulSoup4, Requests
- **데이터 처리**: Pandas
- **Excel 생성**: OpenPyXL
- **배포**: Streamlit Cloud

## 📝 라이선스

이 프로젝트는 개인 사용 및 학습 목적으로 제작되었습니다.

---

⭐ 도움이 되었다면 별표를 눌러주세요!