"""관계형 데이터 유사 속성 탐지 — 순수 로직, DB 접근 없음.

서로 다른 기관이 만든 두 테이블에서 **의미가 같은 컬럼**을 1:1 로 짝짓는다.
`업소명` ↔ `사업장명` 처럼 글자가 전혀 겹치지 않는 쌍을 잡아야 하므로 문자 비교만으로는
안 되고, 반대로 의미 벡터만 쓰면 `과세년도` ↔ `과세연도` 같은 표기 변형에 약하다.
두 근거를 가중 결합한다.

    채널 1  컬럼명 의미   임베딩 코사인 (column_embedding.ColumnEmbeddings)
    채널 2  컬럼명 표기   TF-IDF 문자 n-gram 코사인
    점수 = w_dense·ch1 + w_lexical·ch2      (원본 코사인, min-max 정규화 없음)

점수를 min-max 정규화하지 않는 이유는 실측 때문이다. 후보가 5~9 개뿐이면 1위가 항상
1.0 이 되어 margin 판정이 무력화된다.

배정은 헝가리안 1:1 최적 배정이고, 그 뒤에 확신이 낮은 배정을 거부한다. 헝가리안은
대응이 없는 컬럼에도 억지로 짝을 붙이므로 거부 단계가 없으면 FP 가 쏟아진다.

파라미터(가중치·임계값)는 별도 검증셋에서 확정했다.

"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# 검증셋에서 확정한 값. 변경하지 않는다.
DEFAULT_W_DENSE = 0.5
DEFAULT_W_LEXICAL = 0.5
DEFAULT_MIN_SCORE = 0.35
DEFAULT_MARGIN_MIN = 0.05

# 3차년도 model.py 35~36행의 TF-IDF 구조를 승계한다.
TFIDF_ANALYZER = "char_wb"
TFIDF_NGRAM_RANGE = (2, 4)


@dataclass
class Match:
    left: str
    right: str
    score: float
    margin: float


def lexical_matrix(left: Sequence[str], right: Sequence[str],
                   analyzer: str = TFIDF_ANALYZER,
                   ngram_range: Tuple[int, int] = TFIDF_NGRAM_RANGE) -> np.ndarray:
    """컬럼명 표기 유사도. dense 가 약한 표기 변형을 잡는다.

    `과세년도` ↔ `과세연도`, `주택유형` ↔ `주택 유형` 처럼 의미 모델이 놓치기 쉬운
    한 글자 차이를 문자 n-gram 이 잡아낸다.
    """
    if not left or not right:
        return np.zeros((len(left), len(right)), dtype=np.float32)

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vec = TfidfVectorizer(analyzer=analyzer, ngram_range=tuple(ngram_range))
    vec.fit(list(left) + list(right))
    return cosine_similarity(vec.transform(left),
                             vec.transform(right)).astype(np.float32)


def dense_matrix(left: Sequence[str], right: Sequence[str], embeddings) -> np.ndarray:
    """컬럼명 의미 유사도. 사전에 없는 이름은 0(모름)으로 채운다.

    `ColumnEmbeddings.similarity_matrix()` 는 사전에 없는 이름을 행렬에서 **빼고**
    남은 인덱스를 함께 돌려준다. 여기서는 원래 위치에 되돌려 전체 크기를 유지한다.
    헝가리안 배정과 margin 계산이 '몇 개의 후보가 남아 있는가'에 의존하므로,
    행렬 크기가 달라지면 같은 입력에도 다른 결과가 나온다.
    """
    full = np.zeros((len(left), len(right)), dtype=np.float32)
    if embeddings is None or not len(embeddings) or not left or not right:
        return full
    sub, li, ri = embeddings.similarity_matrix(left, right)
    if sub.size:
        full[np.ix_(li, ri)] = sub
    return full


def match(score: np.ndarray, min_score: float = DEFAULT_MIN_SCORE,
          margin_min: float = DEFAULT_MARGIN_MIN) -> List[Tuple[int, int, float, float]]:
    """헝가리안 1:1 배정 후 확신이 낮은 건을 거부한다.

    margin = 배정 점수 − **아직 배정되지 않은** 상대 컬럼 중 최고점.

    차순위를 그냥 쓰면 안 된다. 실측 사례로, 쌍1 `업소명` 의 점수는
        업종명   0.5881   ← 이미 `업종명` ↔ `업종명` 에 배정됨
        사업장명 0.5527   ← 헝가리안이 `업소명` 에 배정한 정답
    이라 차순위 기준 margin 이 -0.0354 가 되어 **정답이 거부된다.**
    이미 남에게 배정된 후보는 이 컬럼이 고를 수 있는 대안이 아니므로 제외한다.

    남은 후보가 없으면 비교 대상이 없으므로 margin = 점수 로 둔다. 이때는
    min_score 가 사실상 유일한 거부 조건이 된다(|right| <= |left| 인 쌍이 여기 해당).

    반환: (left 인덱스, right 인덱스, 점수, margin) — 채택된 것만
    """
    from scipy.optimize import linear_sum_assignment

    if score.size == 0:
        return []
    rows, cols = linear_sum_assignment(-score)
    taken = set(cols)
    free = [j for j in range(score.shape[1]) if j not in taken]

    out: List[Tuple[int, int, float, float]] = []
    for i, j in zip(rows, cols):
        s = float(score[i, j])
        margin = s - float(max(score[i, jj] for jj in free)) if free else s
        if s < min_score or margin < margin_min:
            continue
        out.append((int(i), int(j), s, float(margin)))
    return out


def detect(left_columns: Sequence[str], right_columns: Sequence[str], embeddings,
           w_dense: float = DEFAULT_W_DENSE, w_lexical: float = DEFAULT_W_LEXICAL,
           min_score: float = DEFAULT_MIN_SCORE,
           margin_min: float = DEFAULT_MARGIN_MIN,
           exclude_left: Optional[Sequence[str]] = None,
           exclude_right: Optional[Sequence[str]] = None) -> Dict:
    """두 컬럼 목록에서 의미가 유사한 속성을 1:1 로 탐지한다.

    exclude_* 는 매칭 대상에서 아예 빼는 컬럼이다. 대응 관계를 객관적으로 확정할 수
    없는 속성을 정답에서만 빼고 매칭 대상에 남기면, 모델이 그 컬럼을 매칭할 때 FP 로
    처벌받는다. 판정 불가 항목을 모델 탓으로 돌리는 셈이므로 양쪽에서 함께 뺀다.
    """
    ex_l = set(exclude_left or ())
    ex_r = set(exclude_right or ())
    left = [c for c in left_columns if c not in ex_l]
    right = [c for c in right_columns if c not in ex_r]

    ch1 = dense_matrix(left, right, embeddings)
    ch2 = lexical_matrix(left, right)
    score = w_dense * ch1 + w_lexical * ch2

    matches = [Match(left=left[i], right=right[j], score=round(s, 6),
                     margin=round(m, 6))
               for i, j, s, m in match(score, min_score, margin_min)]
    return {
        "matches": matches,
        "left_columns": len(left),
        "right_columns": len(right),
        "excluded_left": sorted(ex_l & set(left_columns)),
        "excluded_right": sorted(ex_r & set(right_columns)),
        "params": {"w_dense": w_dense, "w_lexical": w_lexical,
                   "min_score": min_score, "margin_min": margin_min},
    }


# ── 자체 검증 ────────────────────────────────────────────────────────────────

def _self_test() -> int:
    failed = 0

    def check(title, cond, detail=""):
        nonlocal failed
        failed += 0 if cond else 1
        print("[%s] %-46s %s" % ("OK" if cond else "FAIL", title, detail))

    # 표기 유사도는 절대값이 아니라 **순서**로 판단한다. TF-IDF 를 두 테이블의 컬럼명
    # 수십 개에만 맞추므로 절대값은 낮게 나온다(`과세년도`↔`과세연도` 0.260).
    # 이 채널의 역할은 의미 채널이 놓치는 표기 변형을 보완하는 것이므로,
    # 대응 컬럼이 같은 행에서 가장 높기만 하면 된다.
    lex = lexical_matrix(["과세년도", "업소명"], ["과세연도", "사업장명"])
    check("표기 유사도 - 표기 변형이 행 최대",
          lex[0, 0] == lex[0].max() and lex[0, 0] > lex[0, 1],
          "%.3f vs %.3f" % (lex[0, 0], lex[0, 1]))
    check("표기 유사도 - 안 겹치면 0에 가까움", lex[1, 0] < 0.05, "%.3f" % lex[1, 0])
    check("표기 행렬 크기", lex.shape == (2, 2), str(lex.shape))
    check("빈 입력 안전", lexical_matrix([], ["a"]).shape == (0, 1))

    # 헝가리안: 각자 최고점을 고르면 충돌하는 상황에서 전체 최적을 찾는다
    #        업종명  사업장명
    # 업소명  0.588   0.553
    # 업종명  1.000   0.201
    score = np.array([[0.588, 0.553], [1.000, 0.201]], dtype=np.float32)
    got = match(score, min_score=0.35, margin_min=0.0)
    pairs = {(i, j) for i, j, _, _ in got}
    check("헝가리안 전체 최적 배정", pairs == {(0, 1), (1, 0)}, str(sorted(pairs)))

    # margin 은 미배정 후보 기준이어야 한다. 차순위(0.588, 이미 배정됨) 기준이면
    # 업소명의 margin 이 음수가 되어 정답이 거부된다.
    got = match(score, min_score=0.35, margin_min=0.05)
    check("margin - 배정된 후보는 비교 대상 아님",
          (0, 1) in {(i, j) for i, j, _, _ in got}, str(len(got)))

    # 남은 후보가 없으면 margin = 점수
    one = np.array([[0.9]], dtype=np.float32)
    got = match(one, min_score=0.35, margin_min=0.05)
    check("미배정 후보 없으면 margin=점수",
          len(got) == 1 and abs(got[0][3] - 0.9) < 1e-6, str(got))

    # 임계값 거부
    low = np.array([[0.30]], dtype=np.float32)
    check("min_score 미만 거부", match(low, min_score=0.35) == [])
    check("빈 행렬 안전", match(np.zeros((0, 0), dtype=np.float32)) == [])

    # 사전이 없어도 죽지 않는다 (표기 채널만으로 동작)
    d = dense_matrix(["가"], ["나"], None)
    check("사전 없으면 dense 0", d.shape == (1, 1) and d[0, 0] == 0.0)

    # 사전에 없는 이름은 원래 위치에 0 으로 남는다
    class _Emb:
        def __len__(self): return 2
        def similarity_matrix(self, left, right):
            # 두 번째 left 와 첫 번째 right 만 사전에 있다고 가정
            return np.array([[0.8]], dtype=np.float32), [1], [1]
    d = dense_matrix(["없음", "있음"], ["없음", "있음"], _Emb())
    check("미등록 이름은 0 으로 채움",
          d.shape == (2, 2) and d[1, 1] == np.float32(0.8) and d[0, 0] == 0.0,
          str(d.tolist()))

    # 제외 컬럼은 매칭 대상에서 빠진다
    r = detect(["업소명", "적재ID"], ["사업장명", "적재ID"], None,
               exclude_left=["적재ID"], exclude_right=["적재ID"])
    check("제외 컬럼 반영", r["left_columns"] == 1 and r["right_columns"] == 1
          and r["excluded_left"] == ["적재ID"], str(r["left_columns"]))
    check("제외 후에도 탐지 동작", isinstance(r["matches"], list))

    print("\n%d/12 통과" % (12 - failed))
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(1 if _self_test() else 0)
