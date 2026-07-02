"""규칙 기반 매처: 컬럼 하나가 표준에 맞는지 판정한다(순수 로직, DB 의존 없음).

판정 순서
 1) RULE_TERM: 컬럼명 전체가 표준 용어의 english_sign 과 일치?
      일치하면 용어의 도메인 타입 + 길이 vs 컬럼 비교 → 맞음 / 타입불일치(계열|길이)
 2) RULE_WORD: 컬럼명을 토큰으로 쪼개 모든 토큰이 표준 단어와 일치?
      일치하면 형식단어의 도메인 타입(계열) vs 컬럼 비교 → 맞음 / 타입불일치
      (단어는 도메인 분류명에 여러 길이가 매핑되므로 길이는 검사하지 않음)
 3) NAME_MISMATCH: 위 둘 다 실패 → 추천 용어 제시
"""
from StandardMapping.service.tokenizer import tokenize
from StandardMapping.service.type_normalizer import type_matches, type_check

RULE_TERM = "RULE_TERM"
RULE_WORD = "RULE_WORD"
TYPE_MISMATCH = "TYPE_MISMATCH"
NAME_MISMATCH = "NAME_MISMATCH"


def match_column(
    column_name: str,
    column_type: str,
    terms_by_sign: dict,
    words_by_sign: dict,
    domain_by_name: dict,
    domain_type_by_classified: dict,
    recommender,
) -> dict:
    """단일 컬럼 판정 결과 dict 반환.

    terms_by_sign:            {UPPER(english_sign): {"id", "domain"}}
    words_by_sign:            {UPPER(english_sign): {"id", "classified", "form"}}
    domain_by_name:           {domain.name: {"type", "size", "decimal"}}   (용어용, 길이 포함)
    domain_type_by_classified:{domain.domain_classified_name: data_type}   (단어용, 계열만)
    recommender:              TermRecommender
    """
    tokens = tokenize(column_name)
    result = {
        "tokens": tokens,
        "is_standardized": False,
        "not_standardized_reason": None,
        "type_detail": None,          # 타입/길이 불일치 상세(툴팁용)
        "standard_term_id": None,
        "standard_word_ids": None,
        "recommended_term_ids": None,
        "mapping_method": None,
    }

    sign = (column_name or "").strip().upper()

    # 1) RULE_TERM: 컬럼명 전체 == 표준 용어 english_sign
    term = terms_by_sign.get(sign)
    if term:
        result["mapping_method"] = RULE_TERM
        result["standard_term_id"] = term["id"]
        dom = domain_by_name.get(term.get("domain")) or {}
        ok, _reason, detail = type_check(column_type, dom.get("type"),
                                         dom.get("size"), dom.get("decimal"))
        if ok:
            result["is_standardized"] = True
        else:
            result["not_standardized_reason"] = TYPE_MISMATCH
            result["type_detail"] = detail
        return result

    # 2) RULE_WORD: 모든 토큰이 표준 단어
    matched_words = [words_by_sign.get(tok) for tok in tokens]
    if tokens and all(w is not None for w in matched_words):
        result["mapping_method"] = RULE_WORD
        result["standard_word_ids"] = [w["id"] for w in matched_words]
        # 형식단어(form='Y')의 도메인 계열로 타입 체크. 여러 개면 마지막 것.
        form_words = [w for w in matched_words
                      if w.get("form") == "Y" and w.get("classified")]
        if form_words:
            domain_type = domain_type_by_classified.get(form_words[-1]["classified"])
            if type_matches(column_type, domain_type):
                result["is_standardized"] = True
            else:
                result["not_standardized_reason"] = TYPE_MISMATCH
                result["type_detail"] = "타입 계열 불일치"
        else:
            # 형식단어가 없으면 타입 판단 불가 → 이름은 맞으므로 표준으로 인정
            result["is_standardized"] = True
        return result

    # 3) NAME_MISMATCH: 이름 자체가 표준 미준수 → 추천
    result["not_standardized_reason"] = NAME_MISMATCH
    recommended = recommender.recommend(tokens, top_n=3)
    result["recommended_term_ids"] = recommended or None
    return result
