"""컬럼명 임베딩 — 문자열이 달라도 의미가 같은 컬럼을 잡기 위한 벡터 사전.

difflib 문자 유사도만으로는 두 방향의 오류가 남는다.

    자치구 ↔ 지역        difflib 0.000  — 의미가 같은데 글자가 안 겹쳐 놓친다
    인구수 ↔ 입구 수온    difflib 0.571  — 글자가 겹쳐 의미가 먼데도 잡는다

반대로 임베딩은 영문 약어에 약하다(`resourceId` ↔ `resrce_id` 는 difflib 0.889,
임베딩 0.684). 그래서 **둘을 대체하지 않고 별도 근거로 병행**한다.

모델은 `jhgan/ko-sroberta-multitask` — 한국어 문장 유사도용으로 학습된 모델이며
이미 캐시돼 있다. 카탈로그가 한글 공공데이터 위주라 이 선택이 맞다.

유사 속성 탐지도 같은 벡터를 쓴다 — `similarity_matrix()` 참조.

배치로 한 번 만들어 파일에 저장하고(`column_embeddings.npz`), 추천 요청은 읽기만 한다.
요청마다 인코딩하면 수십 초가 걸려 실시간 응답이 불가능하다.
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

# 기본 모델. `recommender.column_embedding_model` 로 교체할 수 있고,
# `embedding_backend=external` 이면 Service.get_embeddings 로 위임된다(TEI 등).
#
# 기존 local 백엔드(klue/bert-base 평균풀링)를 쓰지 않는 이유는 실측 때문이다.
# 원본 BERT 평균풀링은 짧은 구절에서 모든 쌍을 비슷하게 본다.
#   판별력(무관쌍 대비 유사쌍 평균차)  klue/bert-base 0.213  vs  ko-sroberta 0.363
#   `종사자수` ↔ `환자수` (무관)        klue/bert-base 0.798  vs  ko-sroberta 0.526
# 0.798 은 함정 6(측정값끼리 조인)에서 제거한 바로 그 오탐을 되살리는 값이다.
DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"
EMBEDDING_FILE = "column_embeddings.npz"

# ── 용도별 사전 ──────────────────────────────────────────────────────────────
# 융합 추천과 유사 속성 탐지는 같은 컬럼명을 쓰지만 요구하는 모델이
# 다르다. 하나로 합칠 수 없어 사전을 나눈다.
#
# 실측 (2026-08-12, TEI `BAAI/bge-m3` 직접 호출)
#                              ko-sroberta   bge-m3
#   `종사자수` ↔ `환자수`  (무관)      0.526     0.715   ← 0.60 기준 통과
#   `구분`     ↔ `수량`    (무관)      0.238     0.520
#   `자치구`   ↔ `수두`    (축퇴)      1.000     0.336
#   `유형`     ↔ `업종`    (유사)      0.655     0.534
#
# 융합 추천은 의미 점수 0.60 이상을 조인 키 근거로 단독 인정하므로
# (`fusion_scorer.SEMANTIC_EVIDENCE_MIN`), bge-m3 로 바꾸면 0.715 가 통과해
# 함정 6(측정값끼리 조인) 오탐이 되살아난다 — 위 klue/bert-base 0.798 과 같은 실패다.
# 반대로 유사 속성 탐지는 ko-sroberta 로 정답/오답이 분리되지 않는다(분리 간격 -0.042.
# 최저 TP 0.197 이 최고 FP 0.238 보다 낮아 어떤 임계값도 성립하지 않는다).
PURPOSE_FUSION = "fusion"
PURPOSE_SIMILAR_ATTR = "similar_attr"

_PURPOSES: Dict[str, Tuple[str, str]] = {
    # 용도: (사전 파일명, 기본 모델)
    PURPOSE_FUSION: (EMBEDDING_FILE, DEFAULT_MODEL),
    PURPOSE_SIMILAR_ATTR: ("column_embeddings_similar_attr.npz", "BAAI/bge-m3"),
}


def purposes() -> List[str]:
    return list(_PURPOSES)


def normalize_purpose(purpose: Optional[str]) -> str:
    """용도 문자열을 다듬고 검증한다.

    앞뒤 공백은 흔한 입력 실수라(쿼리스트링의 `%20`) 다듬어 받는다.
    모르는 값은 조용히 기본값으로 떨어뜨리지 않는다 — 용도가 곧 모델과 파일을
    정하므로, 오타 하나가 다른 모델로 만든 사전을 낳는다.
    """
    name = (purpose or "").strip() or PURPOSE_FUSION
    if name not in _PURPOSES:
        raise ValueError("알 수 없는 임베딩 용도: %r (가능: %s)"
                         % (purpose, ", ".join(_PURPOSES)))
    return name


def _resolve_purpose(purpose: Optional[str]) -> Tuple[str, str]:
    """용도 → (파일명, 기본 모델)."""
    return _PURPOSES[normalize_purpose(purpose)]


def purpose_file(purpose: Optional[str] = None) -> str:
    return _resolve_purpose(purpose)[0]


def purpose_model(purpose: Optional[str] = None) -> str:
    return _resolve_purpose(purpose)[1]

# 축퇴 벡터 탐지 기준.
# 이 모델은 일부 짧은 한국어 단어를 한 점으로 뭉쳐 놓는다. 실측에서
# `자치구` ↔ `수두` ↔ `마을` ↔ `냉난방` ↔ `평점` 이 서로 0.9999 로 나왔다.
# 전체 쌍의 0.01% 에 불과하지만, 무관한 이름에 **최대 확신의 오탐**을 만들므로
# 가장 해로운 오류다. 구분하지 못하는 이름은 사전에서 빼서 '모름' 으로 돌린다.
DEGENERATE_SIM = 0.99
DEGENERATE_MIN_NEIGHBORS = 2

# 컬럼명은 구분자로 끊어 읽어야 의미가 산다. `고용밀집도등급` 같은 복합어는 그대로 둔다.
_SPLIT_CHARS = "_-./\\()[]~· "


def to_text(column_name: str) -> str:
    """임베딩 입력 문자열. 구분자를 공백으로 바꿔 토큰 경계를 살린다."""
    if not column_name:
        return ""
    text = column_name.strip()
    for ch in _SPLIT_CHARS:
        text = text.replace(ch, " ")
    return " ".join(text.split())


def default_encoder(model_name: Optional[str] = None, batch_size: int = 256,
                    cache_dir: Optional[str] = None):
    """sentence-transformers 인코더. import 를 함수 안에 두어 추천 요청 경로는
    모델을 올리지 않는다.

    cache_dir 을 명시하지 않으면 HuggingFace 기본 경로(`~/.cache/huggingface`)를 쓰는데,
    컨테이너에서는 읽기 전용인 경우가 많다. 쓰기 가능한 경로를 넘겨야 한다.
    """
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    from sentence_transformers import SentenceTransformer
    name = model_name or DEFAULT_MODEL
    try:
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            # sentence-transformers 하위의 transformers/huggingface_hub 도 같은 곳을 보게 한다
            os.environ.setdefault("HF_HOME", cache_dir)
            os.environ.setdefault("TRANSFORMERS_CACHE", cache_dir)
        model = SentenceTransformer(name, cache_folder=cache_dir)
    except OSError as e:
        raise RuntimeError(
            "임베딩 모델 로드 실패: %s (model=%s, cache_dir=%s). "
            "컨테이너에 모델이 없고 캐시 경로가 쓰기 불가할 때 발생한다. "
            "쓰기 가능한 column_embedding_cache_dir 을 지정하거나, "
            "column_embedding_backend=external 로 TEI 를 사용하라." % (e, name, cache_dir)
        ) from e

    def encode(texts: Sequence[str]) -> np.ndarray:
        return model.encode(texts, batch_size=batch_size,
                            normalize_embeddings=True,
                            show_progress_bar=False).astype(np.float32)
    return encode


def build(names: Iterable[str], out_dir: str, encode=None,
          model_name: Optional[str] = None, batch_size: int = 256,
          cache_dir: Optional[str] = None,
          purpose: Optional[str] = None) -> dict:
    """서로 다른 컬럼명만 모아 인코딩하고 저장한다.

    컬럼 인스턴스가 아니라 **이름 단위**로 인코딩한다. 카탈로그에는 같은 이름이
    수없이 반복되므로(`resource_id`, `구분` …) 중복을 제거하면 대상이 크게 준다.

    purpose 는 저장 파일명과 기본 모델을 정한다. 생략하면 fusion 이다.
    """
    purpose = normalize_purpose(purpose)
    out_file, purpose_default_model = _PURPOSES[purpose]
    unique = sorted({to_text(n) for n in names if n and to_text(n)})
    if not unique:
        return {"names": 0, "dim": 0, "path": None, "purpose": purpose}

    injected = encode is not None
    if encode is None:
        encode = default_encoder(model_name or purpose_default_model,
                                 batch_size, cache_dir)
    vectors = np.asarray(encode(unique), dtype=np.float32)
    # 코사인을 내적으로 계산하므로 정규화를 보장한다(외부 백엔드가 안 해줄 수 있다).
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors = vectors / norms

    # 모델이 서로 구분하지 못하는 이름은 빼고 저장한다
    unique, vectors, dropped = _drop_degenerate(unique, vectors)

    path = os.path.join(out_dir, out_file)
    try:
        os.makedirs(out_dir, exist_ok=True)
        np.savez_compressed(path, names=np.array(unique, dtype=object), vectors=vectors)
    except OSError as e:
        raise RuntimeError(
            "임베딩 사전 저장 실패: %s (path=%s). "
            "recommender.data_dir 이 쓰기 가능한지 확인하라." % (e, path)) from e
    return {"names": len(unique), "dim": int(vectors.shape[1]), "path": path,
            "dropped_degenerate": dropped,
            "purpose": purpose,
            "model": model_name or ("injected" if injected else purpose_default_model)}


def _drop_degenerate(names: List[str], vectors: np.ndarray,
                     chunk: int = 1024) -> Tuple[List[str], np.ndarray, int]:
    """모델이 서로 구분하지 못하는 이름을 사전에서 제거한다.

    다른 이름과 DEGENERATE_SIM 이상인 이웃이 DEGENERATE_MIN_NEIGHBORS 개 넘게 있으면,
    그 벡터는 이름의 의미가 아니라 모델의 사각지대를 가리킨다. 남겨두면
    무관한 컬럼끼리 1.0 이 나온다.

    전체 행렬(12,578²)은 메모리에 올리지 않고 조각내어 이웃 수만 센다.
    """
    n = len(names)
    if n < 2:
        return names, vectors, 0
    neighbors = np.zeros(n, dtype=np.int32)
    for start in range(0, n, chunk):
        block = vectors[start:start + chunk] @ vectors.T
        # 자기 자신 제외
        for i in range(block.shape[0]):
            block[i, start + i] = 0.0
        neighbors[start:start + chunk] = (block >= DEGENERATE_SIM).sum(axis=1)

    keep = neighbors <= DEGENERATE_MIN_NEIGHBORS
    dropped = int((~keep).sum())
    if dropped == 0:
        return names, vectors, 0
    kept_names = [nm for nm, k in zip(names, keep) if k]
    return kept_names, vectors[keep], dropped


class ColumnEmbeddings:
    """저장된 벡터 사전. 없으면 비어 있는 상태로 동작한다(임베딩 항목만 빠진다)."""

    def __init__(self, names: Sequence[str], vectors: np.ndarray):
        self.index: Dict[str, int] = {n: i for i, n in enumerate(names)}
        self.vectors = vectors
        # 한 요청 안에서 같은 이름 쌍이 수없이 반복된다(카탈로그의 컬럼명은 재사용된다).
        # 인스턴스 수명이 요청 단위라 캐시가 무한히 자라지 않는다.
        self._sim_cache: Dict[Tuple[str, str], Optional[float]] = {}

    def __len__(self) -> int:
        return len(self.index)

    @classmethod
    def load(cls, data_dir: str, purpose: Optional[str] = None) -> "ColumnEmbeddings":
        path = os.path.join(data_dir, purpose_file(purpose))
        if not os.path.exists(path):
            return cls([], np.zeros((0, 0), dtype=np.float32))
        with np.load(path, allow_pickle=True) as data:
            names = [str(n) for n in data["names"]]
            vectors = data["vectors"]
        return cls(names, vectors)

    def vector(self, column_name: str) -> Optional[np.ndarray]:
        i = self.index.get(to_text(column_name))
        return None if i is None else self.vectors[i]

    def similarity(self, a: str, b: str) -> Optional[float]:
        """두 컬럼명의 코사인 유사도. 사전에 없으면 None(모름).

        음수는 0 으로 자른다. '반대 의미'라는 정보는 조인 판단에 쓸 데가 없다.
        """
        ta, tb = to_text(a), to_text(b)
        key = (ta, tb) if ta <= tb else (tb, ta)
        if key in self._sim_cache:
            return self._sim_cache[key]

        ia, ib = self.index.get(ta), self.index.get(tb)
        if ia is None or ib is None:
            result = None
        else:
            result = max(0.0, float(np.dot(self.vectors[ia], self.vectors[ib])))
        self._sim_cache[key] = result
        return result

    def similarity_matrix(
        self, left: Sequence[str], right: Sequence[str]
    ) -> Tuple[np.ndarray, List[int], List[int]]:
        """유사 속성 탐지의 헝가리안 매칭용 행렬.

        반환: (유사도 행렬, 사전에 있는 left 인덱스, 사전에 있는 right 인덱스)
        사전에 없는 이름은 행렬에서 빠지므로 호출부가 원래 위치를 되찾을 수 있게
        인덱스를 함께 돌려준다.
        """
        li = [i for i, n in enumerate(left) if to_text(n) in self.index]
        ri = [i for i, n in enumerate(right) if to_text(n) in self.index]
        if not li or not ri:
            return np.zeros((0, 0), dtype=np.float32), li, ri
        lv = np.vstack([self.vectors[self.index[to_text(left[i])]] for i in li])
        rv = np.vstack([self.vectors[self.index[to_text(right[i])]] for i in ri])
        return np.clip(lv @ rv.T, 0.0, 1.0), li, ri


# ── 자체 검증 ────────────────────────────────────────────────────────────────

def _self_test() -> int:
    failed = 0

    def check(title, cond, detail=""):
        nonlocal failed
        failed += 0 if cond else 1
        print("[%s] %-40s %s" % ("OK" if cond else "FAIL", title, detail))

    check("구분자 → 공백", to_text("resrce_id") == "resrce id", to_text("resrce_id"))
    check("괄호 처리", to_text("인구수(명)") == "인구수 명", to_text("인구수(명)"))
    check("빈 입력", to_text(None) == "" and to_text("  ") == "")

    # 사전이 없을 때도 죽지 않는다
    empty = ColumnEmbeddings.load("/tmp/__no_such_dir__")
    check("사전 없으면 빈 객체", len(empty) == 0)
    check("사전 없으면 유사도 None", empty.similarity("a", "b") is None)

    names = ["자치구", "지역", "인구수"]
    vecs = np.array([[1, 0], [0.7, 0.714], [0, 1]], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    emb = ColumnEmbeddings(names, vecs)
    check("유사도 계산", abs(emb.similarity("자치구", "지역") - 0.7) < 0.02,
          "%.3f" % emb.similarity("자치구", "지역"))
    check("직교 → 0", emb.similarity("자치구", "인구수") < 0.01)
    check("미등록 이름 → None", emb.similarity("자치구", "없는컬럼") is None)

    mat, li, ri = emb.similarity_matrix(["자치구", "없는컬럼"], ["지역", "인구수"])
    check("행렬 크기", mat.shape == (1, 2), str(mat.shape))
    check("미등록 인덱스 제외", li == [0] and ri == [0, 1])

    # build() 전 경로. 인코더를 주입해 모델 없이 검증한다.
    # 이 경로를 빼놓았다가 반환문만 고치고 호출을 빠뜨린 채 배포한 적이 있다.
    import tempfile
    # 축퇴 판정은 이웃 2개 초과다. 3개가 뭉친 정도는 정당한 동의어 변형
    # (`resource id` / `resourceid` / `resource_id`)일 수 있으므로 남긴다.
    fake = {"가": [1.0, 0.0], "나": [1.0, 0.0],
            "다": [1.0, 0.0], "바": [1.0, 0.0],                    # 축퇴 4개
            "라": [0.0, 1.0], "마": [0.6, 0.8]}                    # 정상 2개
    order = []

    def encode(texts):
        order.extend(texts)
        return np.array([fake[t] for t in texts], dtype=np.float32)

    tmp = tempfile.mkdtemp()
    stats = build(list(fake.keys()), tmp, encode=encode)
    check("build 반환 필드", set(stats) >= {"names", "dim", "path", "dropped_degenerate"},
          str(sorted(stats)))
    check("축퇴 4개 제거", stats["dropped_degenerate"] == 4, str(stats["dropped_degenerate"]))
    check("정상 2개 유지", stats["names"] == 2, str(stats["names"]))

    reloaded = ColumnEmbeddings.load(tmp)
    check("저장/로드 왕복", len(reloaded) == 2 and reloaded.similarity("가", "나") is None)
    check("정상 이름은 유사도 산출", reloaded.similarity("라", "마") is not None,
          str(reloaded.similarity("라", "마")))

    # ── 용도별 사전 ─────────────────────────────────────────────────────────
    check("기본 용도는 fusion", purpose_file() == EMBEDDING_FILE, purpose_file())
    check("용도별 파일명이 다름",
          purpose_file(PURPOSE_SIMILAR_ATTR) != purpose_file(PURPOSE_FUSION),
          purpose_file(PURPOSE_SIMILAR_ATTR))
    check("유사 속성 탐지 기본 모델은 bge-m3",
          purpose_model(PURPOSE_SIMILAR_ATTR) == "BAAI/bge-m3",
          purpose_model(PURPOSE_SIMILAR_ATTR))
    check("융합 추천 기본 모델은 ko-sroberta",
          purpose_model(PURPOSE_FUSION) == DEFAULT_MODEL, purpose_model(PURPOSE_FUSION))

    unknown_rejected = False
    try:
        purpose_file("없는용도")
    except ValueError:
        unknown_rejected = True
    check("모르는 용도는 ValueError", unknown_rejected)
    check("앞뒤 공백 허용",
          normalize_purpose(" similar_attr ") == PURPOSE_SIMILAR_ATTR,
          repr(normalize_purpose(" similar_attr ")))
    check("빈 값은 fusion", normalize_purpose(None) == PURPOSE_FUSION
          and normalize_purpose("  ") == PURPOSE_FUSION)

    # 같은 디렉토리에 두 사전이 공존하며 서로를 덮어쓰지 않아야 한다
    stats6 = build(list(fake.keys()), tmp, encode=encode, purpose=PURPOSE_SIMILAR_ATTR)
    check("유사 속성 탐지 사전은 다른 파일에 저장",
          os.path.basename(stats6["path"]) == purpose_file(PURPOSE_SIMILAR_ATTR),
          os.path.basename(stats6["path"]))
    check("융합 추천 사전이 남아 있음",
          os.path.exists(os.path.join(tmp, purpose_file(PURPOSE_FUSION))))
    check("용도 지정 로드", len(ColumnEmbeddings.load(tmp, PURPOSE_SIMILAR_ATTR)) == 2)
    check("없는 용도 사전은 빈 객체",
          len(ColumnEmbeddings.load(tempfile.mkdtemp(), PURPOSE_SIMILAR_ATTR)) == 0)

    print("\n%d/25 통과" % (25 - failed))
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(1 if _self_test() else 0)
