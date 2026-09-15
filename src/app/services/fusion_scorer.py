"""융합 추천 JoinScore 산출 (순수 로직, 표준 라이브러리만 의존).

기준 테이블에 대해 "**조인해서 같이 쓸 만한**" 테이블을 점수순으로 고른다.
클러스터링 추천이 재는 "내용이 비슷한 테이블"과 방향이 다르다 —
회원 테이블과 거의 같은 회원 테이블을 조인해봐야 얻는 정보가 없기 때문이다.

입력은 컬럼 프로파일 조회 결과 행이며,
DB 접근은 하지 않는다. 조회와 응답 조립은 Service 가 담당한다.


"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ── 가중치 (검증셋으로 조정) ───────────────────────────────────────────
# 2026-09-15 조정: meta_id 류 UUID 고카디널리티
# 키는 top-5 표본만으로 겹침을 못 잡아 _value_overlap() 이 항상 None 을 반환한다.
# 그러면 W_VALUE_OVERLAP 전체가 통째로 빠져 사실상 이름 매칭만 남고 confidence
# 상한이 sqrt(0.55)=0.742 로 묶인다. Phase 3(MinHash containment, docs §7)로
# 근본 해결하기 전까지, 값 겹침 의존도를 낮추고 카디널리티·이름 비중을 올리는
# 임시 완화 조치. (기존: 0.45 / 0.30 / 0.25)
W_VALUE_OVERLAP = 0.25   # 값 도메인 겹침
W_CARDINALITY = 0.40     # PK-FK 패턴
W_NAME = 0.35            # 컬럼명 근거 — 문자 유사도와 의미 유사도를 **묶은 하나**

# 문자 유사도와 의미 유사도를 별도 항목으로 두면 안 된다.
# 같은 문자열에 대한 두 측정이라 독립 근거가 아니다. `구분 = 구분` 은 문자 1.0,
# 의미 1.0 이지만 증거는 하나뿐이다. 별도 항목으로 세면 가중치 합이 커져
# 확신 계수(√(사용가중치/전체))가 올라가고, 이름만 맞는 조합이 기준을 넘는다.
# 실제로 그 때문에 걸러졌던 `구분 = 구분` 이 0.268 → 0.317 로 되살아났다.
# 두 측정 중 **큰 값**을 이름 근거로 삼는다 — 서로를 보완하는 탐지 수단이기 때문이다
# (문자는 영문 약어에, 의미는 한글 동의어에 강하다).

MIN_SCORE = 0.30         # 이 아래는 추천하지 않는다
KEY_LIKE_P_DISTINCT = 0.95   # 이 이상이면 키 후보로 본다
DUP_P_DISTINCT = 0.50        # 이 이하면 중복이 많은 컬럼

# 근사 중복 테이블 감점: 컬럼명이 이만큼 겹치면 "같은 테이블"에 가깝다
REDUNDANT_OVERLAP = 0.80
REDUNDANT_FLOOR = 0.50

# 이름 유사도 조기 탈락 임계값 (이 아래는 0 으로 본다)
_NAME_CUTOFF = 0.55

# 조인 키가 여러 개면 융합 가치가 높다. 최고점 대비 이 비율 이상인 보조 키에 가산.
SECONDARY_RATIO = 0.80
SECONDARY_WEIGHT = 0.10
MAX_EXTRA_KEYS = 2

# top_value_counts 는 상위 5개뿐이다. 고유값이 이보다 많이 크면 그 표본으로 잰
# 겹침 비율은 도메인을 대표하지 못하므로 '모름'으로 처리한다.
# (0 으로 두면 정상적인 키 컬럼이 부당하게 낮아진다 — Phase 3 MinHash 의 근거)
TOP_VALUE_REPRESENTATIVE_FACTOR = 2

# 겹친 값이 몇 개인지도 중요하다. 값 하나가 우연히 포함된 것과
# 도메인 전체가 일치하는 것을 같은 1.0 으로 볼 수 없다.
MIN_OVERLAP_SUPPORT = 3

# 행이 몇 개 없으면 is_unique / p_distinct 는 키 여부의 근거가 못 된다.
# 5행짜리 표는 어느 컬럼이든 고유하다.
MIN_ROWS_FOR_CARDINALITY = 30

# 흔한 컬럼명은 변별력이 없다. '구분', '번호', '합계' 는 수백 개 표에 나오며
# 이름이 같다는 사실만으로는 조인 근거가 되지 않는다.
# 불용어를 손으로 나열하는 대신 카탈로그 안의 출현 빈도로 판단한다(IDF).
GENERIC_DF_RATIO = 0.02   # 전체 테이블의 이 비율을 넘게 나타나면 '흔한 이름'
# 표본이 적으면 출현 빈도 자체가 통계가 아니다. 테이블 4개에서 2개에 나온다고
# 흔한 이름이 아니다. 이 수 미만이면 희소도를 적용하지 않는다.
MIN_TABLES_FOR_RARITY = 50

# 문자도 값도 안 겹치는데 의미만 가까운 경우(자치구 ↔ 지역)를 근거로 인정하는 하한
SEMANTIC_EVIDENCE_MIN = 0.60

# 적재기·시스템이 덧붙인 컬럼은 조인 키가 아니다(_source_file, _ingested_at 등).
SYSTEM_COLUMN_PREFIXES = ("_",)

# 적재기 컬럼(`적재ID` 등)을 이름으로 나열하지 않는다.
#
# 실측(2026-08-06, .110 검토시트 900행)에서 `적재ID` 가 조인 키 근거 1,072회로
# 1위였으나, 그 원인은 **희소도를 이름 점수(25%)에만 곱하던 것**이었다(함정 14).
# 희소도를 점수 전체에 곱하도록 고치면 전 테이블에 있는 컬럼은 자동으로 눌린다
# (1,604개 표 전부에 존재 → 희소도 ≈ 0.14, 점수 1/7).
#
# 이름 목록을 손으로 관리하는 것은 설계 원칙(§ GENERIC_DF_RATIO 주석)에 어긋나고
# 사이트마다 적재기 컬럼명이 달라 유지보수 대상이 된다. 실측으로 부족함이
# 확인되면 코드가 아니라 `config [recommender] system_column_names` 로 뺀다.

# 숫자끼리인데 키라는 근거가 없으면 측정값끼리 붙인 것이다(인구수 = 환자수).
# 실제 조인은 식별자·코드에서 일어난다.
NUMERIC_PAIR_PENALTY = 0.6

# 집계 수치 도메인으로 볼 상한. 통계표의 계수 컬럼은 0·1·2 같은 작은 정수라
# 서로 무관한 표끼리도 top-5 가 그대로 겹친다. 이보다 큰 값이 섞이면
# 단순 계수 컬럼으로 보지 않는다.
COUNTING_DOMAIN_MAX = 1000

# 행번호 판정에 쓰는 '흔한 이름' 기준. 값 모양·카디널리티와 **함께** 볼 때만
# 쓴다 — 빈도만으로 자르면 정규화된 스키마의 공용 키(meta_id 등)가 같이 죽는다.
ROW_NUMBER_RARITY_MAX = 0.5

# 시각 컬럼도 조인 키가 아니다. 로그·이력 테이블의 timestamp 는 거의 고유하지만
# 그건 키라서가 아니라 시계열이라 그렇다. 카디널리티가 1:N 으로 잡혀 강한 근거처럼
# 보이므로 숫자쌍보다 더 눌러야 한다. 다만 값이 실제로 겹치면(같은 날짜 축을 공유)
# 면제한다.
TIME_PAIR_PENALTY = 0.5

# epoch 시각은 숫자로 저장돼 구조적으로 고유 ID 와 구분되지 않는다.
# 실측: TIMESTAMP_BIZ_PROJECT.TIME_STAMP 는 data_type=Numeric, n=14037, n_distinct=14014
# 로 p_distinct 0.998 — 키 후보로 잡혀 숫자쌍 감점까지 면제됐다.
# 표본값의 자릿수로 판별한다. 초=2001~2033년, 밀리초·마이크로초도 같은 구간.
# 금액 같은 큰 수를 시각으로 오판해도 결과는 같다 — 측정값 역시 조인 키가 아니다.
_EPOCH_BANDS = ((1e9, 2e9), (1e12, 2e12), (1e15, 2e15))

# ydata-profiling 추론 타입의 조인 호환 그룹
_TYPE_GROUPS = {
    "numeric": "NUM",
    "categorical": "STR",
    "text": "STR",
    "boolean": "BOOL",
    "datetime": "TIME",
    "timeseries": "TIME",
}

# DB 원본 타입 → 그룹. 프로파일이 없어도 column_type 은 메타에 있으므로,
# 미프로파일 테이블에서도 타입 게이트와 숫자쌍 판정을 살릴 수 있다.
_DB_TYPE_GROUPS = (
    ("int", "NUM"), ("serial", "NUM"), ("numeric", "NUM"), ("decimal", "NUM"),
    ("float", "NUM"), ("double", "NUM"), ("real", "NUM"), ("money", "NUM"),
    ("char", "STR"), ("text", "STR"), ("string", "STR"), ("clob", "STR"),
    ("uuid", "STR"), ("json", "STR"),
    ("timestamp", "TIME"), ("date", "TIME"), ("time", "TIME"),
    ("bool", "BOOL"),
)


def _db_type_group(column_type: Optional[str]) -> Optional[str]:
    if not column_type:
        return None
    lowered = column_type.strip().lower()
    for token, group in _DB_TYPE_GROUPS:
        if token in lowered:
            return group
    return None


@dataclass
class ColumnProfile:
    column_name: str
    column_type: Optional[str] = None      # DB 원본 타입
    data_type: Optional[str] = None        # ydata-profiling 추론 타입
    is_unique: Optional[bool] = None
    n_rows: Optional[int] = None
    n_distinct: Optional[int] = None
    p_distinct: Optional[float] = None
    p_missing: Optional[float] = None
    top_values: Set[str] = field(default_factory=set)
    norm_name: str = ""          # 정규화 컬럼명 (매 비교마다 다시 만들지 않도록 캐시)
    type_group: Optional[str] = None   # 조인 호환 그룹 (동일)

    def __post_init__(self):
        if not self.norm_name:
            self.norm_name = _normalize(self.column_name)
        if self.type_group is None:
            if self.data_type:
                self.type_group = _TYPE_GROUPS.get(self.data_type.strip().lower())
            if self.type_group is None:
                # 프로파일이 없어도 DB 타입은 있다
                self.type_group = _db_type_group(self.column_type)

    @property
    def profiled(self) -> bool:
        return self.data_type is not None


@dataclass
class TableProfile:
    meta_id: str
    meta_name: str
    system_id: Optional[str] = None
    columns: List[ColumnProfile] = field(default_factory=list)
    _group_index: Optional[Dict[Optional[str], List[ColumnProfile]]] = field(
        default=None, repr=False, compare=False)

    @property
    def column_names(self) -> Set[str]:
        return {c.column_name.lower() for c in self.columns}

    @property
    def group_index(self) -> Dict[Optional[str], List[ColumnProfile]]:
        """타입 그룹별 컬럼 색인.

        타입이 다른 쌍은 어차피 게이트에서 탈락하므로, 아예 순회하지 않는다.
        컬럼 전수 대조 대비 비교 횟수가 그룹 수만큼 줄어든다.
        (build_tables 가 컬럼을 다 채운 뒤 첫 접근 시 만든다)
        """
        if self._group_index is None:
            index: Dict[Optional[str], List[ColumnProfile]] = {}
            for col in self.columns:
                index.setdefault(_type_group(col), []).append(col)
            self._group_index = index
        return self._group_index


@dataclass
class JoinCandidate:
    left: str
    right: str
    type_match: Optional[bool]      # None = 판단 불가(프로파일 없음)
    value_overlap: Optional[float]
    cardinality: str            # '1:1' | '1:N' | 'N:M' | 'unknown'
    confidence: float
    name_score: float = 0.0     # 문자 유사도 (근거 유무 판정용)
    semantic_score: Optional[float] = None   # 의미 유사도. None = 사전에 없음
    known: bool = False         # Phase 0 이력에서 실제로 쓰인 조인인가

    def reason(self) -> str:
        if self.known:
            return "실제 사용 이력 있는 조인 키"
        bits = []
        if self.semantic_score is not None and self.semantic_score >= 0.6:
            bits.append("컬럼 의미 유사")
        if self.cardinality in ("1:N", "1:1"):
            bits.append(f"{self.cardinality} (PK-FK 후보)")
        if self.value_overlap is not None and self.value_overlap > 0:
            bits.append(f"값 도메인 {round(self.value_overlap * 100)}% 겹침")
        return ", ".join(bits) if bits else "컬럼명 유사"


@dataclass
class Recommendation:
    meta_id: str
    meta_name: str
    system_id: Optional[str]
    score: float
    join_keys: List[JoinCandidate]

    @property
    def reason(self) -> str:
        return self.join_keys[0].reason() if self.join_keys else ""


def compatible_data_types(columns: Iterable[ColumnProfile]) -> List[str]:
    """기준 테이블 컬럼들과 조인 가능한 data_type 목록.

    `fusion_candidate_columns` 의 후보 축소 파라미터로 넘긴다.
    타입 게이트를 SQL 앞단으로 내려 Python 비교 횟수를 줄이기 위함이다.
    """
    groups = {g for g in (_type_group(c) for c in columns) if g}
    return sorted(t for t, g in _TYPE_GROUPS.items() if g in groups)


# ── 입력 변환 ────────────────────────────────────────────────────────────────

def build_tables(rows: Iterable[dict]) -> Dict[str, TableProfile]:
    """`fusion_column_profile` 결과 행들을 테이블 단위로 묶는다."""
    tables: Dict[str, TableProfile] = {}
    for row in rows:
        meta_id = str(row["meta_id"])
        table = tables.get(meta_id)
        if table is None:
            table = TableProfile(
                meta_id=meta_id,
                meta_name=row.get("meta_name") or meta_id,
                system_id=str(row["system_id"]) if row.get("system_id") else None,
            )
            tables[meta_id] = table

        name = row.get("column_name")
        if not name:
            continue
        table.columns.append(ColumnProfile(
            column_name=name,
            column_type=row.get("column_type"),
            data_type=row.get("data_type"),
            is_unique=row.get("is_unique"),
            n_rows=row.get("n_rows"),
            n_distinct=row.get("n_distinct"),
            p_distinct=_to_float(row.get("p_distinct")),
            p_missing=_to_float(row.get("p_missing")),
            top_values=_top_value_keys(row.get("top_value_counts")),
        ))
    return tables


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _top_value_keys(raw) -> Set[str]:
    """top_value_counts(jsonb) 의 키 집합. 값 자체가 도메인 표본이다."""
    if not raw:
        return set()
    if isinstance(raw, dict):
        return {str(k).strip().lower() for k in raw.keys() if str(k).strip()}
    return set()


# ── 컬럼 쌍 점수 ─────────────────────────────────────────────────────────────

def _type_group(col: ColumnProfile) -> Optional[str]:
    return col.type_group


def _type_compatible(a: ColumnProfile, b: ColumnProfile) -> Optional[bool]:
    """None 은 '판단 불가'(프로파일 없음)이며 게이트를 통과시킨다."""
    ga, gb = _type_group(a), _type_group(b)
    if ga is None or gb is None:
        return None
    return ga == gb


def _key_like(col: ColumnProfile) -> Optional[bool]:
    """키 후보인가. 판단 근거가 부족하면 None.

    행이 얼마 없으면 고유성은 우연이다 — 5행짜리 표에서는 인구수도 고유하다.
    그런 표본으로 PK-FK 를 추정하면 측정값 컬럼이 키로 둔갑한다.
    """
    if col.n_rows is not None and col.n_rows < MIN_ROWS_FOR_CARDINALITY:
        return None
    if col.is_unique:
        return True
    if col.p_distinct is not None:
        return col.p_distinct >= KEY_LIKE_P_DISTINCT
    return None


def _cardinality(a: ColumnProfile, b: ColumnProfile) -> Tuple[str, Optional[float]]:
    ka, kb = _key_like(a), _key_like(b)
    if ka is None or kb is None:
        return "unknown", None
    if ka and kb:
        return "1:1", 0.9
    if ka or kb:
        return "1:N", 1.0
    # 양쪽 다 중복이 많으면 조인 결과가 폭발한다
    pa, pb = a.p_distinct, b.p_distinct
    if pa is not None and pb is not None and pa <= DUP_P_DISTINCT and pb <= DUP_P_DISTINCT:
        return "N:M", 0.3
    return "N:M", 0.5


def _looks_like_epoch(col: ColumnProfile) -> bool:
    """숫자로 저장된 시각인가. 표본값이 모두 같은 epoch 구간에 들어가면 참."""
    if col.type_group != "NUM" or not col.top_values:
        return False
    values = []
    for raw in col.top_values:
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            return False
    return any(all(lo <= v < hi for v in values) for lo, hi in _EPOCH_BANDS)


def _integer_values(col: ColumnProfile) -> Optional[List[int]]:
    """표본값이 모두 음이 아닌 정수면 그 목록, 아니면 None.

    선언 타입(data_type)을 보지 않는다. 공공데이터 CSV 는 숫자 컬럼도
    Text/Categorical 로 프로파일링되는 일이 흔해, 타입으로 가르면 숫자 관련
    규칙이 통째로 죽는다(실측: NUMERIC_PAIR_PENALTY 가 .110 에서 한 번도
    발동하지 않았다).
    """
    if not col.top_values:
        return None
    values: List[int] = []
    for raw in col.top_values:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if value < 0 or value != int(value):
            return None
        values.append(int(value))
    return values or None


def _is_counting_domain(col: ColumnProfile) -> bool:
    """값이 작은 정수 집합인가 — 통계표 집계 수치 컬럼의 특징."""
    values = _integer_values(col)
    return values is not None and max(values) <= COUNTING_DOMAIN_MAX


def _looks_like_row_number(col: ColumnProfile) -> bool:
    """표별로 1 부터 매긴 행번호인가.

    적재기가 붙인 순번은 어느 표에서나 1..N 이라 **값이 우연히 겹친다.**
    참조 관계가 아니므로 조인 키가 아니다.
    """
    values = _integer_values(col)
    if values is None:
        return False
    return col.n_rows is None or max(values) <= col.n_rows


def _is_row_number_pair(a: ColumnProfile, b: ColumnProfile,
                        rarity: float = 1.0) -> bool:
    """양쪽 모두 '표별 행번호' 인가. 이 조합은 조인 근거가 없다.

    빈도(IDF)로 판정하지 않는다 — 정규화된 스키마에서 공용 키는 **원래**
    여러 표에 나온다. `meta_id` 가 30개 표에 있는 것은 흔해서가 아니라
    그 스키마의 중심 키라서다. 빈도로 자르면 진짜 조인 키를 골라서 죽인다.

    값과 카디널리티로 가른다:
      - `meta_id` 류 공용 키 → 문자열(UUID)이라 숫자 조건에서 빠진다
      - 진짜 PK-FK      → 참조하는 쪽 값이 반복돼 1:N 이다. 양쪽 고유가 아니다
      - 코드표 `코드ID 1~50` ↔ FK → 역시 1:N 이라 안전하다
    **양쪽이 모두 고유한 조밀 정수 수열**일 때만 성립하며, 그건 두 표가 각자
    매긴 행번호가 우연히 겹친 경우 외에는 나오기 어렵다.

    실측(2026-08-06, .110): `적재ID` 는 1,604개 표 전부에 존재하고 p_distinct=1.0
    이라 '키 후보' 로 인정돼 숫자쌍 감점까지 면제받았다. 검토시트 900행에서
    조인 키 근거 1,072회로 1위였다.
    """
    if rarity > ROW_NUMBER_RARITY_MAX:
        # 카탈로그에 드문 이름이면 적재기 컬럼이 아니다. 빈도를 **단독** 근거로
        # 쓰지 않되, 값 모양만으로 자르면 50행 코드표의 `코드ID 1~50` 같은
        # 정상 키까지 걸리므로 함께 본다.
        return False
    if _key_like(a) is not True or _key_like(b) is not True:
        return False
    return _looks_like_row_number(a) and _looks_like_row_number(b)


def _value_overlap(a: ColumnProfile, b: ColumnProfile) -> Optional[float]:
    """상위 빈도값 집합의 겹침 비율. 표본이 도메인을 대표하지 못하면 None.

    top_value_counts 는 상위 5개뿐이다. 자치구처럼 고유값이 5개인 컬럼은 표본이
    도메인 전체이므로 겹침이 그대로 의미를 갖지만, 고유값이 10만인 ID 컬럼은
    상위 5개가 겹칠 리 없어 **완벽한 FK 도 겹침 0** 이 나온다.
    그런 경우를 0 으로 두면 정상적인 조인 키가 부당하게 낮아지므로 '모름'으로 돌린다.

    Phase 3 에서 MinHash containment 로 교체하면 이 제약이 사라진다 (docs §7).
    """
    if not a.top_values or not b.top_values:
        return None
    for col in (a, b):
        limit = max(len(col.top_values), 1) * TOP_VALUE_REPRESENTATIVE_FACTOR
        if col.n_distinct is not None and col.n_distinct > limit:
            return None
    inter = len(a.top_values & b.top_values)
    if inter == 0:
        return 0.0
    ratio = inter / min(len(a.top_values), len(b.top_values))
    # 표본이 작을수록 겹침 비율을 그대로 믿을 수 없다.
    # 대전 자치구 5종 vs "동구" 하나뿐인 컬럼은 비율상 1.0 이지만 근거는 1건이다.
    support = min(1.0, inter / MIN_OVERLAP_SUPPORT)
    return ratio * support


_PIVOT_NAME_RE = re.compile(r"^(19|20)\d{2}(년|년도|년말|기준)?$|^\d{1,2}(월|분기|반기)$")


def _is_pivot_name(name: str) -> bool:
    """피벗 테이블의 자리표시자 컬럼명인가.

    `2023년`, `2024년`, `1월`, `4분기` 같은 이름은 컬럼이 아니라 **축**이고,
    그 안의 값은 측정값이다. 이름이 같다고 조인 근거가 되지 않는다.

    실측(2026-08-06): `제휴복지_서비스_이용실적` ↔ `권역별_연도별_주요_경제_지표` 가
    `2023년=2023년`, `2024년=2021년` 으로 0.874 를 받아 1순위에 올랐다.
    숫자만 검사하던 이전 규칙은 `2023년` 에 붙은 한 글자 때문에 통과시켰다.
    """
    if not name:
        return False
    return name.isdigit() or bool(_PIVOT_NAME_RE.match(name))


def _semantic(a: ColumnProfile, b: ColumnProfile, embeddings) -> Optional[float]:
    """컬럼명 의미 유사도. 사전이 없거나 미등록 이름이면 None(모름).

    숫자로만 된 이름(열차번호 1076, 연도 1988 …)은 문자 유사도와 같은 이유로 제외한다.
    임베딩은 `1076` 과 `1077` 을 비슷하게 보지만 피벗 테이블의 자리표시자일 뿐이다.
    이 규칙이 빠져 함정 10 에서 제거한 오탐이 되살아난 적이 있다.
    """
    if embeddings is None:
        return None
    if _is_pivot_name(a.norm_name) or _is_pivot_name(b.norm_name):
        return 0.0
    return embeddings.similarity(a.column_name, b.column_name)


def _name_similarity(na: str, nb: str) -> float:
    """정규화된 이름끼리 비교한다. 입력은 ColumnProfile.norm_name.

    프로파일링 결과 이 함수가 전체 시간의 70% 를 차지했다(요청당 20만 회 이상 호출).
    컬럼명은 스키마 계열마다 반복되므로(`resource_id`, `code_id` …) 결과를 캐시한다.
    키를 정렬해 (a,b)/(b,a) 를 같은 항목으로 만든다.
    """
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # 숫자로만 된 이름(열차번호 1190, 연도 2119 …)은 피벗 테이블의 자리표시자다.
    # 자릿수가 겹친다고 유사한 컬럼이 아니므로 정확히 같을 때만 인정한다.
    if _is_pivot_name(na) or _is_pivot_name(nb):
        return 0.0
    return _name_similarity_cached(na, nb) if na < nb else _name_similarity_cached(nb, na)


@lru_cache(maxsize=1 << 18)
def _name_similarity_cached(na: str, nb: str) -> float:
    matcher = SequenceMatcher(None, na, nb)
    # 값싼 상한으로 먼저 탈락시킨다. 이름은 가중치 W_NAME 항이라
    # 낮은 값의 정밀도는 결과 순위에 영향이 없다.
    if matcher.real_quick_ratio() < _NAME_CUTOFF:
        return 0.0
    if matcher.quick_ratio() < _NAME_CUTOFF:
        return 0.0
    return matcher.ratio()


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_name_rarity(tables: Dict[str, "TableProfile"]) -> Dict[str, float]:
    """컬럼명별 희소도. 흔한 이름일수록 0 에 가깝다.

    같은 '이름 일치' 라도 `구분`(수백 개 표에 존재)과 `자치구`(수십 개)는
    근거의 무게가 다르다. 카탈로그 실측 빈도로 가중치를 정한다.
    """
    n_tables = len(tables)
    if n_tables < MIN_TABLES_FOR_RARITY:
        return {}
    df: Dict[str, int] = {}
    for table in tables.values():
        for norm in {c.norm_name for c in table.columns if c.norm_name}:
            df[norm] = df.get(norm, 0) + 1

    threshold = max(1.0, n_tables * GENERIC_DF_RATIO)
    rarity: Dict[str, float] = {}
    for norm, count in df.items():
        rarity[norm] = 1.0 if count <= threshold else (threshold / count) ** 0.5
    return rarity


def score_column_pair(
    a: ColumnProfile, b: ColumnProfile, known: bool = False,
    name_rarity: Optional[Dict[str, float]] = None,
    embeddings=None,
) -> Optional[JoinCandidate]:
    """컬럼 쌍의 조인 가능성 점수. 타입이 명백히 다르면 None."""
    compatible = _type_compatible(a, b)
    if compatible is False:
        return None

    if known:
        # 실제로 조인에 쓰인 쌍은 추정할 필요가 없다
        card, _ = _cardinality(a, b)
        return JoinCandidate(
            left=a.column_name, right=b.column_name,
            type_match=compatible,
            name_score=_name_similarity(a.norm_name, b.norm_name),
            semantic_score=_semantic(a, b, embeddings),
            value_overlap=_value_overlap(a, b),
            cardinality=card, confidence=1.0, known=True,
        )

    # 희소도는 **컬럼의 성질**이지 이름 근거만의 성질이 아니다.
    # 이름 점수(W_NAME)에만 곱하면 흔한 컬럼이 값 겹침(W_VALUE_OVERLAP)·
    # 카디널리티(W_CARDINALITY)로 되살아난다.
    # 실측(2026-08-06, .110): `경상북도_학교_현황` ↔ `국민건강보험공단_지사_현황` 이
    # `우편번호=우편번호` 값 겹침으로 0.890 을 받아 1순위에 올랐다. 우편번호는
    # 수백 개 표에 있는 속성이지 식별자가 아니다.
    # 점수 전체에 한 번만 곱한다 — 이름만 있는 쌍에서는 종전과 결과가 같고
    # (raw=이름, 최종=이름×확신×희소도), 값 근거가 있는 쌍만 제대로 눌린다.
    rarity = 1.0
    if name_rarity:
        rarity = min(name_rarity.get(a.norm_name, 1.0), name_rarity.get(b.norm_name, 1.0))

    # 아래 두 조합은 점수를 깎는 것으로 부족하다 — 후보에서 뺀다.
    # 기준 컬럼별 최고 후보를 모으는 구조라, 짝이 그것뿐이면 아무리 낮아도
    # 조인 키 목록에 계속 남아 검토자가 매 행마다 무시해야 하는 잡음이 된다.
    if _is_row_number_pair(a, b, rarity):
        return None
    # 피벗 축 컬럼(`2023년`, `4분기`)은 컬럼이 아니라 축이고 값은 측정값이다.
    # 이름 유사도만 0 으로 두면 값 겹침(W_VALUE_OVERLAP)·카디널리티(W_CARDINALITY)로
    # 되살아난다 — 실측(당시 가중치 0.45/0.30)에서 `2023년=2023년` 이 0.73 으로 남았다.
    if _is_pivot_name(a.norm_name) or _is_pivot_name(b.norm_name):
        return None

    overlap = _value_overlap(a, b)
    card, card_score = _cardinality(a, b)
    name_score = _name_similarity(a.norm_name, b.norm_name)
    semantic_score = _semantic(a, b, embeddings)

    # 작은 정수 도메인끼리의 겹침은 이름 근거가 받쳐줄 때만 인정한다.
    #
    # 통계표의 집계 수치(`펌프(대)`, `영업용`, `시설개소`)는 값이 0·1·2 라
    # 서로 무관한 표끼리도 top-5 가 그대로 겹친다. 그 겹침은 같은 도메인을
    # 공유한다는 증거가 아니라 **둘 다 작은 수라는 사실**일 뿐이다.
    # 실측(2026-08-06, .110): `펌프(대)=건설업` 이 overlap=1.0 으로 0.683.
    #
    # 선언 타입(NUM)으로 가르지 않는다 — 공공데이터 CSV 는 숫자 컬럼도
    # Text/Categorical 로 프로파일링돼 타입 조건을 걸면 규칙이 통째로 죽는다.
    # 실제로 NUMERIC_PAIR_PENALTY 가 이 데이터셋에서 한 번도 발동하지 않았다.
    #
    # 이름 근거를 조건으로 두면 진짜 코드 조인은 지켜진다:
    #   `시도코드=시도코드` → 이름 1.0 이므로 겹침을 그대로 쓴다
    #   `펌프(대)=건설업`   → 이름 0.0 / 의미 0.48 이라 겹침을 근거에서 뺀다
    # 한쪽이라도 키(PK)면 애초에 이 규칙에 걸리지 않는다.
    if (overlap is not None
            and _key_like(a) is not True and _key_like(b) is not True
            and _is_counting_domain(a) and _is_counting_domain(b)
            and max(name_score, semantic_score or 0.0) < SEMANTIC_EVIDENCE_MIN):
        overlap = None

    # 근거가 있는 항목만 쓰고 가중치를 재정규화한다.
    # 없는 값을 0 으로 두면 프로파일이 부실한 테이블이 부당하게 낮아진다.
    # 문자·의미 중 큰 값 하나만 이름 근거로 쓴다
    name_evidence = max(name_score, semantic_score or 0.0)

    parts: List[Tuple[float, float]] = [(W_NAME, name_evidence)]
    if overlap is not None:
        parts.append((W_VALUE_OVERLAP, overlap))
    if card_score is not None:
        parts.append((W_CARDINALITY, card_score))

    used_weight = sum(w for w, _ in parts)
    raw = sum(w * v for w, v in parts) / used_weight

    # 숫자끼리인데 어느 쪽도 키라는 근거가 없으면 측정값 조인이다.
    # 인구수 = 환자수 처럼 이름·범위가 그럴듯해도 조인해서 얻을 게 없다.
    if _type_group(a) == "NUM" and _type_group(b) == "NUM":
        key_evidence = _key_like(a) is True or _key_like(b) is True
        # epoch 시각은 고유해도 키가 아니다. 같은 밀리초로 조인할 일은 없다.
        if _looks_like_epoch(a) or _looks_like_epoch(b):
            key_evidence = False
        if not key_evidence:
            raw *= NUMERIC_PAIR_PENALTY

    # 시각끼리는 값이 실제로 겹칠 때만 인정한다. `timestamp = TIME_STAMP` 는
    # 고유성 때문에 1:N 으로 잡혀 그럴듯해 보이지만, 시각은 조인 키가 아니라
    # 필터·정렬 축이다. 키 여부로는 면제하지 않는다 — 시계열은 원래 고유하다.
    if _type_group(a) == "TIME" and _type_group(b) == "TIME" and not overlap:
        raw *= TIME_PAIR_PENALTY

    # 결측 감점
    missing = max(a.p_missing or 0.0, b.p_missing or 0.0)
    raw *= max(0.0, 1.0 - missing)

    # 근거가 적을수록 확신을 낮춘다.
    # 재정규화만 하면 "이름 하나만 완벽히 일치" 가 1.0 이 되어, 근거가 전혀 없는
    # 미프로파일 테이블이 실제 통계를 갖춘 후보를 밀어낸다. 제곱근으로 깎아
    # 이름만으로는 0.5 를 넘지 못하게 한다.
    total_weight = W_NAME + W_VALUE_OVERLAP + W_CARDINALITY
    confidence = (used_weight / total_weight) ** 0.5

    return JoinCandidate(
        left=a.column_name, right=b.column_name,
        type_match=compatible,
        name_score=name_score,
        semantic_score=semantic_score,
        value_overlap=overlap,
        cardinality=card,
        confidence=round(raw * confidence * rarity, 6),
    )


# ── 테이블 쌍 점수 ───────────────────────────────────────────────────────────

def _is_system_column(col: ColumnProfile) -> bool:
    """적재기가 덧붙인 시스템 컬럼인가.

    `_source_file` 같은 컬럼은 모든 벌크 적재 테이블에 존재하지만 조인 키가 아니다.
    출현 빈도(IDF)로는 걸러지지 않는다 — 특정 적재 경로의 표에만 있어 희소하기 때문이다.
    """
    name = (col.column_name or "").strip()
    return name.startswith(SYSTEM_COLUMN_PREFIXES)


def _redundancy_penalty(base: TableProfile, cand: TableProfile) -> float:
    """컬럼 구성이 거의 같은 테이블은 조인해도 정보 이득이 없다.

    설계 원칙 §1.3 — "유사한 테이블 ≠ 융합 가능한 테이블" 을 점수에 반영한다.
    """
    a, b = base.column_names, cand.column_names
    if not a or not b:
        return 1.0
    # 자카드로 잰다. min() 을 분모로 쓰면 컬럼이 적은 정상 후보가
    # 기준표의 부분집합이라는 이유만으로 최대 감점을 받는다.
    # 중복은 "양쪽이 서로 비슷"해야 성립한다.
    overlap = len(a & b) / len(a | b)
    if overlap <= REDUNDANT_OVERLAP:
        return 1.0
    excess = (overlap - REDUNDANT_OVERLAP) / (1.0 - REDUNDANT_OVERLAP)
    return max(REDUNDANT_FLOOR, 1.0 - excess * (1.0 - REDUNDANT_FLOOR))


def score_table_pair(
    base: TableProfile,
    cand: TableProfile,
    known_pairs: Optional[Set[Tuple[str, str]]] = None,
    max_keys: int = 3,
    name_rarity: Optional[Dict[str, float]] = None,
    embeddings=None,
) -> Optional[Recommendation]:
    known_pairs = known_pairs or set()
    candidates: List[JoinCandidate] = []

    for a in base.columns:
        if _is_system_column(a):
            continue
        # 타입 게이트를 순회 앞단으로 — 같은 그룹 + 판단불가(프로파일 없음)만 본다
        group = _type_group(a)
        if group is None:
            cand_columns: Sequence[ColumnProfile] = cand.columns
        else:
            index = cand.group_index
            cand_columns = index.get(group, []) + index.get(None, [])

        for b in cand_columns:
            if _is_system_column(b):
                continue
            known = (
                (base.meta_id, a.column_name.lower(), cand.meta_id, b.column_name.lower())
                in known_pairs
            )
            pair = score_column_pair(a, b, known=known, name_rarity=name_rarity,
                                     embeddings=embeddings)
            if pair is not None:
                candidates.append(pair)

    if not candidates:
        return None

    # 같은 기준 컬럼이 여러 후보 컬럼과 맞는 것은 증거 하나다. 컬럼별 최고만 남긴다.
    best_per_left: Dict[str, JoinCandidate] = {}
    for c in candidates:
        key = c.left.lower()
        cur = best_per_left.get(key)
        if cur is None or (c.known, c.confidence) > (cur.known, cur.confidence):
            best_per_left[key] = c

    ordered = sorted(best_per_left.values(),
                     key=lambda c: (c.known, c.confidence), reverse=True)
    # 카디널리티만으로는 조인 근거가 되지 않는다. "둘 다 고유한 숫자 컬럼"은
    # 인구수 = 적재ID 같은 무의미한 쌍을 만든다. 이름이든 값이든 실질 신호가 있어야 한다.
    ordered = [c for c in ordered
               if c.known or c.name_score > 0 or (c.value_overlap or 0) > 0
               or (c.semantic_score or 0) >= SEMANTIC_EVIDENCE_MIN]
    if not ordered:
        return None

    best = ordered[0]

    # 조인 가능한 컬럼이 여럿이면 융합 가치가 높다.
    # 자치구+종사자수로 이어지는 표가 종사자수 하나만 맞는 표보다 쓸모 있다.
    extras = [c for c in ordered[1:] if c.confidence >= best.confidence * SECONDARY_RATIO]
    bonus = 1.0 + SECONDARY_WEIGHT * min(len(extras), MAX_EXTRA_KEYS)

    score = min(1.0, best.confidence * bonus) * _redundancy_penalty(base, cand)

    return Recommendation(
        meta_id=cand.meta_id,
        meta_name=cand.meta_name,
        system_id=cand.system_id,
        score=round(score, 6),
        join_keys=ordered[:max_keys],
    )


def recommend(
    base_meta_id: str,
    tables: Dict[str, TableProfile],
    known_pairs: Optional[Set[Tuple[str, str]]] = None,
    top_n: int = 10,
    min_score: float = MIN_SCORE,
    embeddings=None,
) -> List[Recommendation]:
    base = tables.get(str(base_meta_id))
    if base is None:
        return []

    name_rarity = build_name_rarity(tables)

    results: List[Recommendation] = []
    for meta_id, cand in tables.items():
        # 자기 자신은 후보에서 제외한다 — 제품 관점의 의도된 선택이다(2026-08-28).
        # parent_id=id 류 재귀 조인은 스코어링상으로는 탐지 가능하지만(한때 허용해
        # 봤었음, 자체검증 27/27 통과), "자기 자신과의 융합"은 사용자에게 실질적인
        # 추천 가치가 없다고 판단해 되돌렸다. 아래 자체검증에서 이 배제를 지킨다.
        if meta_id == base.meta_id:
            continue
        rec = score_table_pair(base, cand, known_pairs, name_rarity=name_rarity,
                               embeddings=embeddings)
        if rec is not None and rec.score >= min_score:
            results.append(rec)

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]


def build_known_pairs(rows: Iterable[dict]) -> Set[Tuple[str, str]]:
    """`fusion_known_join_keys` 결과를 양방향 조회 가능한 집합으로 만든다."""
    pairs: Set[Tuple[str, str]] = set()
    for row in rows:
        left, right = row.get("left_meta_id"), row.get("right_meta_id")
        lc, rc = row.get("left_column"), row.get("right_column")
        if not (left and right and lc and rc):
            continue
        pairs.add((str(left), lc.lower(), str(right), rc.lower()))
        pairs.add((str(right), rc.lower(), str(left), lc.lower()))
    return pairs


# ── 자체 검증 ────────────────────────────────────────────────────────────────

def _col(name, **kw):
    kw.setdefault("data_type", "Categorical")
    kw["top_values"] = set(kw.pop("top_values", []) or [])
    return ColumnProfile(column_name=name, **kw)


def _self_test() -> int:
    failed = 0

    def check(title, cond, detail=""):
        nonlocal failed
        ok = bool(cond)
        failed += 0 if ok else 1
        print("[%s] %-46s %s" % ("OK" if ok else "FAIL", title, detail))

    customer = TableProfile("A", "<table>", columns=[
        _col("cust_id", is_unique=True, p_distinct=1.0, top_values=["c1", "c2", "c3"]),
        _col("name", p_distinct=0.9),
        _col("grade", p_distinct=0.05),
    ])
    order = TableProfile("B", "<table>", columns=[
        _col("order_id", is_unique=True, p_distinct=1.0),
        _col("customer_id", p_distinct=0.2, top_values=["c1", "c2", "c9"]),
        _col("amount", data_type="Numeric", p_distinct=0.8),
    ])
    # customer 와 컬럼 구성이 거의 같은 근사 중복 테이블
    customer_copy = TableProfile("C", "<table>", columns=[
        _col("cust_id", is_unique=True, p_distinct=1.0, top_values=["c1", "c2", "c3"]),
        _col("name", p_distinct=0.9),
        _col("grade", p_distinct=0.05),
    ])
    unprofiled = TableProfile("D", "<table>", columns=[
        ColumnProfile(column_name="cust_id"),
        ColumnProfile(column_name="memo"),
    ])
    tables = {t.meta_id: t for t in (customer, order, customer_copy, unprofiled)}

    pair = score_column_pair(customer.columns[0], order.columns[1])
    check("PK-FK + 값겹침 → 1:N 판정", pair and pair.cardinality == "1:N",
          "card=%s conf=%.3f" % (pair.cardinality, pair.confidence) if pair else "")

    numeric_vs_str = score_column_pair(customer.columns[1], order.columns[2])
    check("타입 불일치 → 탈락", numeric_vs_str is None)

    recs = recommend("A", tables, top_n=10, min_score=0.0)
    names = [r.meta_name for r in recs]
    check("추천 결과 생성", len(recs) == 3, str(names))

    order_rec = next((r for r in recs if r.meta_id == "B"), None)
    copy_rec = next((r for r in recs if r.meta_id == "C"), None)
    check("근사 중복 테이블이 조인 대상보다 낮음",
          order_rec and copy_rec and order_rec.score > copy_rec.score,
          "order=%.3f copy=%.3f" % (order_rec.score, copy_rec.score)
          if order_rec and copy_rec else "")

    unprof_rec = next((r for r in recs if r.meta_id == "D"), None)
    check("프로파일 없는 테이블도 후보에 남음(이름 유사도 폴백)",
          unprof_rec is not None,
          "score=%.3f" % unprof_rec.score if unprof_rec else "")
    check("근거 적은 폴백은 확신 감점", unprof_rec and unprof_rec.score < order_rec.score,
          "unprofiled=%.3f < order=%.3f" % (unprof_rec.score, order_rec.score)
          if unprof_rec and order_rec else "")

    known = build_known_pairs([{
        "left_meta_id": "A", "left_column": "grade",
        "right_meta_id": "B", "right_column": "order_id", "op": "=",
    }])
    boosted = score_table_pair(customer, order, known)
    check("실사용 조인 키는 최상위로", boosted.join_keys[0].known,
          "%s = %s" % (boosted.join_keys[0].left, boosted.join_keys[0].right))

    # ── 2026-08-06 실측 교정 (.110 검토시트 900행) ────────────────────────────
    # 함정 12: 적재기 컬럼(`적재ID`)이 조인 근거 1,072회로 1위. 이름 목록으로
    # 막지 않고 희소도로 처리한다 — 전 테이블에 있으면 희소도가 바닥이다.
    check("접두사 시스템 컬럼은 여전히 배제",
          _is_system_column(_col("_source_file"))
          and not _is_system_column(_col("적재ID")))

    # 표별 행번호끼리는 값이 우연히 겹칠 뿐이므로 후보에서 제외한다.
    # 선언 타입에 의존하면 안 된다 — 공공데이터는 숫자도 Text 로 프로파일링된다.
    row_no = _col("적재ID", is_unique=True, p_distinct=1.0,
                  n_rows=100, top_values=["1", "2", "3"])
    check("행번호끼리의 조인은 후보에서 제외 (타입 무관)",
          score_column_pair(row_no, row_no, name_rarity={"적재id": 0.14}) is None)
    check("드문 이름이면 행번호 규칙을 적용하지 않음",
          score_column_pair(row_no, row_no) is not None)

    # 공용 키(meta_id 류)는 살아남아야 한다 — 빈도로 자르지 않는 이유.
    uuid_a = _col("meta_id", is_unique=True, p_distinct=1.0, n_rows=100,
                  top_values=["a1b2", "c3d4", "e5f6"])
    uuid_b = _col("meta_id", p_distinct=0.2, n_rows=500,
                  top_values=["a1b2", "c3d4", "e5f6"])
    check("문자열 공용 키는 유지", score_column_pair(uuid_a, uuid_b) is not None)

    # 진짜 PK-FK 는 참조하는 쪽이 반복돼 1:N 이다 — 행번호 규칙에 안 걸린다.
    pk = _col("코드ID", is_unique=True, p_distinct=1.0,
              n_rows=50, top_values=["1", "2", "3"])
    fk = _col("코드ID", p_distinct=0.1, n_rows=500,
              top_values=["1", "2", "3"])
    check("숫자 PK-FK(1:N)는 유지", score_column_pair(pk, fk) is not None)

    # 통계표의 집계 수치끼리는 작은 정수라 top-5 가 늘 겹친다. 근거로 쓰지 않는다.
    metric_a = _col("펌프(대)", p_distinct=0.1, n_rows=200,
                    top_values=["0", "1", "2"])
    metric_b = _col("건설업", p_distinct=0.1, n_rows=200,
                    top_values=["0", "1", "2"])
    measured = score_column_pair(metric_a, metric_b)
    check("같은 이름의 코드 도메인은 겹침 유지",
          (lambda p: p is not None and p.value_overlap is not None)(
              score_column_pair(_col("시도코드", p_distinct=0.1, n_rows=200,
                                     top_values=["11", "26", "27"]),
                                _col("시도코드", p_distinct=0.1, n_rows=300,
                                     top_values=["11", "26", "27"]))))
    check("집계 수치끼리는 값 겹침을 근거로 안 씀",
          measured is None or measured.value_overlap is None,
          "overlap=%s" % (measured.value_overlap if measured else "탈락"))

    # 키가 있는 숫자쌍에서는 값 겹침이 그대로 근거로 쓰여야 한다(회귀 방지).
    kept = score_column_pair(pk, fk)
    check("숫자 PK-FK 는 값 겹침 유지", kept is not None and kept.value_overlap is not None,
          "overlap=%s" % (kept.value_overlap if kept else "탈락"))

    # 함정 13: 피벗 연도 컬럼. `2024년=2021년` 이 0.874 로 1순위에 올랐다.
    check("연도 컬럼은 피벗 자리표시자",
          _is_pivot_name("2023년") and _is_pivot_name("2024") and _is_pivot_name("4분기"))
    check("연도가 아닌 이름은 통과",
          not _is_pivot_name("연도") and not _is_pivot_name("2023년매출"))
    check("피벗 이름끼리는 문자 유사도 0", _name_similarity("2023년", "2021년") == 0.0)
    pivot_a = _col("2023년", p_distinct=0.9, n_rows=100, top_values=["10", "20", "30"])
    pivot_b = _col("2023년", p_distinct=0.9, n_rows=100, top_values=["10", "20", "30"])
    check("피벗 축 컬럼은 후보에서 제외", score_column_pair(pivot_a, pivot_b) is None)

    # 함정 14: 흔한 컬럼명이 값 겹침(45%)으로 되살아나던 문제.
    #   희소도를 이름 점수에만 곱하면 나머지 75% 가 그대로 남는다.
    post_a = _col("우편번호", p_distinct=0.9, n_rows=500, top_values=["12345", "23456", "34567"])
    post_b = _col("우편번호", p_distinct=0.2, n_rows=500, top_values=["12345", "23456", "34567"])
    plain = score_column_pair(post_a, post_b)
    damped = score_column_pair(post_a, post_b, name_rarity={"우편번호": 0.3})
    check("흔한 이름은 값 겹침이 있어도 감쇄됨",
          plain and damped and damped.confidence < plain.confidence * 0.5,
          "일반=%.3f 흔함=%.3f" % (plain.confidence, damped.confidence)
          if plain and damped else "")

    # 이름만 있는 쌍에서는 종전 동작과 같아야 한다(회귀 방지).
    name_only_a = ColumnProfile(column_name="자치구")
    name_only_b = ColumnProfile(column_name="자치구")
    d = score_column_pair(name_only_a, name_only_b, name_rarity={"자치구": 0.4})
    total_w = W_NAME + W_VALUE_OVERLAP + W_CARDINALITY
    check("이름만 있는 쌍의 감쇄율은 희소도 그대로",
          d and abs(d.confidence - 1.0 * (W_NAME / total_w) ** 0.5 * 0.4) < 1e-6,
          "%.4f" % d.confidence if d else "")

    # ── 자기 참조(self-join) 배제는 의도된 제품 결정이다 (2026-08-28) ─────────
    # parent_id=id 류 재귀 조인(조직도·카테고리 계층)은 스코어링 로직만 보면
    # 탐지할 수 있다 — 실제로 한때 허용해 자체검증까지 통과시켜 봤다. 하지만
    # "표가 자기 자신과 융합 가능하다"는 추천은 사용자 입장에서 실질적 가치가
    # 없다고 판단해 되돌렸다(제품 관점). 이 배제가 나중에 실수로 풀리지 않도록
    # 재귀 관계가 실제로 있는 표로도 확인해 둔다.
    dept = TableProfile("E", "<table>", columns=[
        _col("dept_id", is_unique=True, p_distinct=1.0, n_rows=50,
             top_values=["1", "2", "3"]),
        _col("parent_dept_id", p_distinct=0.3, n_rows=50,
             top_values=["1", "2", "9"]),
    ])
    tables_with_dept = dict(tables)
    tables_with_dept[dept.meta_id] = dept

    dept_recs = recommend("E", tables_with_dept, top_n=10, min_score=0.0)
    check("재귀 조인 관계가 있어도 자기 자신은 추천 후보에서 제외",
          all(r.meta_id != "E" for r in dept_recs),
          str([r.meta_id for r in dept_recs]))

    # 재귀 관계가 없는 평범한 표도 당연히 자기 자신을 추천하지 않는다.
    plain_self = next((r for r in recommend("A", tables, top_n=10, min_score=0.0)
                       if r.meta_id == "A"), None)
    check("재귀 관계 없는 표도 자기 자신을 추천하지 않음", plain_self is None)

    total = 7 + 16 + 2
    print("\n%d/%d 통과" % (total - failed, total))
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(1 if _self_test() else 0)
