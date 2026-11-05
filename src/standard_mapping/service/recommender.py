"""표준 용어 추천기: 이름이 표준에 안 맞는 컬럼에 대해, 토큰이 겹치는
표준 용어를 추천한다(top-N). 임베딩 없이 토큰 교집합 기반(Phase 1).

용어의 english_sign 을 '_' 로 쪼갠 토큰 집합으로 역색인을 만들어 두고,
컬럼 토큰과 가장 많이 겹치는 용어를 고른다.
"""
import collections

from StandardMapping.service.tokenizer import tokenize


class TermRecommender:
    def __init__(self, terms: list):
        """terms: [{"id":..., "sign":<UPPER english_sign>}, ...]"""
        self._inverted = collections.defaultdict(set)   # token -> {term_id}
        self._term_tokens = {}                          # term_id -> frozenset(tokens)
        for t in terms:
            tid = t["id"]
            toks = frozenset(tokenize(t["sign"]))
            if not toks:
                continue
            self._term_tokens[tid] = toks
            for tok in toks:
                self._inverted[tok].add(tid)

    def recommend(self, tokens, top_n: int = 3) -> list:
        """컬럼 토큰과 겹치는 토큰이 많은 용어 id 를 top_n 개 반환."""
        toks = set(tokens)
        if not toks:
            return []
        # 후보 = 토큰 하나라도 겹치는 용어
        candidates = set()
        for tok in toks:
            candidates |= self._inverted.get(tok, set())
        if not candidates:
            return []
        scored = []
        for tid in candidates:
            tt = self._term_tokens[tid]
            overlap = len(toks & tt)
            # 동점 시 더 간결한(토큰 적은) 용어를 우선 → 군더더기 적은 추천
            scored.append((overlap, -len(tt), tid))
        scored.sort(reverse=True)
        return [tid for _, _, tid in scored[:top_n]]
