"""표준 용어 추천기(퍼지, Phase 2): 토큰 '정확' 겹침 추천이 없을 때 fallback.

컬럼명도 표준용어 영문약어도 모두 '영문 약어'라, 의미(임베딩)보다 철자(문자) 유사도가
정확하다. 컬럼 토큰과 표준용어 토큰을 difflib 철자 유사도로 비교해, 근접 약어
(USR≈USER, PRD≈PROD 등)까지 잡는다. 겹치는(비슷한) 토큰이 없으면 추천하지 않는다
(엉뚱한 의미추측보다 '추천 없음'이 정직).

의존성 없음(표준 difflib). 임베딩/모델 불필요.
"""
import re
from difflib import SequenceMatcher

_SPLIT = re.compile(r"[^A-Z0-9]+")


def _split_sign(sign: str) -> list:
    return [t for t in _SPLIT.split((sign or "").upper()) if t]


class FuzzyTermRecommender:
    def __init__(self, terms: list):
        """terms: [{"id":..., "sign":<UPPER english_sign>}, ...]"""
        self.ids = []
        self.tokens = []            # index -> [term tokens]
        self._first2 = {}           # 2글자 접두 -> {index}  (후보 축소용)
        for t in terms:
            toks = _split_sign(t.get("sign"))
            if not toks:
                continue
            idx = len(self.ids)
            self.ids.append(t["id"])
            self.tokens.append(toks)
            for tk in toks:
                self._first2.setdefault(tk[:2], set()).add(idx)

    def recommend(self, col_tokens, top_n: int = 2,
                  min_score: float = 0.72, min_token: float = 0.75) -> list:
        """컬럼 토큰과 철자가 비슷한 표준 용어 id top_n 반환.

        - 각 컬럼 토큰마다 용어 토큰들 중 최대 철자유사도를 구해 평균 = score
        - min_token: 적어도 한 토큰은 이만큼 비슷해야 함(막연한 매칭 배제)
        - min_score: 평균이 이 값 이상인 용어만 추천
        - 비슷한 후보가 없으면 [] (추천 없음)
        """
        col = [c.upper() for c in (col_tokens or []) if c]
        if not col:
            return []
        cand = set()
        for c in col:
            cand |= self._first2.get(c[:2], set())
        scored = []
        for i in cand:
            tts = self.tokens[i]
            per = []
            best_long = 0.0          # 3글자 이상 토큰의 최대 유사도(짧은 토큰 편승 방지)
            for c in col:
                b = max(SequenceMatcher(None, c, tt).ratio() for tt in tts)
                per.append(b)
                if len(c) >= 3 and b > best_long:
                    best_long = b
            score = sum(per) / len(per)
            # 근거가 되는 강한 매칭은 반드시 '실질 토큰'(≥3글자)에서 나와야 함
            # (AT≈AMT, IN≈INT 같은 2글자 편승 배제)
            if score >= min_score and best_long >= min_token:
                # 동점 시 토큰 수 적은(간결한) 용어 우선
                scored.append((score, -len(tts), i))
        scored.sort(reverse=True)
        return [self.ids[i] for _, _, i in scored[:top_n]]
