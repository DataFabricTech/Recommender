"""벡터 기반 표준 용어 추천 (Phase 2): 토큰 겹침 추천이 없을 때 fallback.

임베딩(klue/bert 등)으로 표준 용어와 컬럼을 같은 벡터공간에 두고, 코사인 유사도가
높은 용어를 추천한다. 임베딩 자체는 호출측(service)에서 계산해 넘기고, 본 모듈은
표준 용어 벡터를 들고 있다가 컬럼 벡터와 비교해 top-N을 돌려주는 순수 로직만 담당한다.
"""
import numpy as np


def _l2norm(mat):
    mat = np.asarray(mat, dtype=np.float64)
    n = np.linalg.norm(mat, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return mat / n


class VectorTermRecommender:
    def __init__(self, term_ids, term_vectors):
        """term_ids: 표준 용어 id 리스트 (T개), term_vectors: T×d 임베딩."""
        self.ids = list(term_ids)
        self.mat = _l2norm(term_vectors) if len(self.ids) else np.zeros((0, 1))

    def recommend(self, col_vector, top_n=2, min_sim=0.0):
        """컬럼 벡터와 가장 비슷한 표준 용어 id top_n 반환 (코사인)."""
        if not self.ids or col_vector is None:
            return []
        v = np.asarray(col_vector, dtype=np.float64).ravel()
        nv = np.linalg.norm(v)
        if nv == 0:
            return []
        sims = self.mat @ (v / nv)
        order = np.argsort(-sims)[:top_n]
        return [self.ids[i] for i in order if sims[i] >= min_sim]
