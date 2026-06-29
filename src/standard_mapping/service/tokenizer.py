"""컬럼명 토크나이저: 컬럼명을 표준단어 매칭용 토큰으로 분리/정규화."""
import re

_SPLIT = re.compile(r"[_\s\-/.]+")


def tokenize(column_name: str) -> list:
    """컬럼명을 '_'(및 공백/하이픈 등) 기준으로 나누고 대문자로 정규화.

    예: 'api_use_yn' -> ['API', 'USE', 'YN']
    빈 토큰은 제외한다.
    """
    if not column_name:
        return []
    parts = _SPLIT.split(str(column_name).strip())
    return [p.upper() for p in parts if p]
