"""데이터 카테고리 차트의 사전정의 카테고리.

각 항목 = (카테고리 이름, 매칭용 키워드 문장).
키워드는 클러스터 centroid 와의 임베딩 유사도 매칭에 쓰이므로,
테이블 메타가 한/영 섞여 있어 한국어+영어 키워드를 함께 둔다.
실제 데이터 성격에 맞춰 이름/키워드를 조정하면 매칭 품질이 올라간다.
"""

CATEGORIES = [
    ("고객/회원", "고객 회원 사용자 가입 계정 개인정보 연락처 customer member user account profile"),
    ("거래/결제", "거래 결제 주문 매출 정산 지불 청구 환불 transaction payment order billing settlement"),
    ("상품/서비스", "상품 제품 서비스 품목 카탈로그 product item service goods catalog"),
    ("주문/배송", "주문 배송 출고 물류 운송 배달 order delivery shipping logistics fulfillment"),
    ("로그/이벤트 이력", "로그 이벤트 이력 기록 감사 추적 history log event audit trace"),
    ("코드/공통 마스터", "코드 공통 마스터 분류 기준 코드값 템플릿 설정 code master common classification lookup config"),
    ("통계/집계", "통계 집계 현황 요약 지표 분석 statistics aggregate summary metric analytics"),
    ("조직/인사", "조직 인사 부서 직원 사원 임직원 organization hr department employee staff"),
    ("권한/보안/인증", "권한 보안 인증 역할 접근 토큰 정책 security auth permission role access policy"),
    ("지리/위치/주소", "지리 위치 주소 좌표 지역 행정구역 시도 geo location address coordinate region"),
    ("시계열/센서/계측", "시계열 센서 계측 측정 모니터링 수집 timeseries sensor measurement monitoring collect"),
    ("시스템/메타데이터", "시스템 메타데이터 설정 구성 스키마 카탈로그 테이블 system metadata schema catalog table"),
    ("문서/콘텐츠", "문서 콘텐츠 게시물 첨부 파일 텍스트 대화 document content article file text"),
    ("금융/회계", "금융 회계 계좌 자금 예산 원장 연금 finance accounting account ledger budget"),
    ("의료/건강", "의료 건강 진료 환자 병원 보험 심사 medical health patient hospital clinical"),
    ("공공/행정", "공공 행정 정부 민원 시민 지자체 공공데이터 public government administration civil"),
    ("교육/학습", "교육 학습 학생 과정 강의 성적 education learning student course training"),
    ("마케팅/캠페인", "마케팅 캠페인 광고 프로모션 채널 고객반응 marketing campaign promotion ad channel"),
    ("재고/자산/설비", "재고 자산 설비 장비 부품 창고 inventory asset equipment facility warehouse"),
    ("네트워크/인프라", "네트워크 인프라 장비 노드 포트 회선 트랜시버 network infrastructure node port transceiver"),
]

CATEGORY_NAMES = [c[0] for c in CATEGORIES]
CATEGORY_KEYWORDS = [c[1] for c in CATEGORIES]
