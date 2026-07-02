"""컬럼명 토크나이저: 컬럼명을 표준단어 매칭용 토큰으로 분리/정규화."""
import re

_SPLIT = re.compile(r"[_\s\-/.]+")
_CAMEL = re.compile(r"([a-z0-9])([A-Z])")        # 소문자→대문자 경계 (bidBeginDt)
_ACRONYM = re.compile(r"([A-Z]+)([A-Z][a-z])")   # 약어→단어 경계 (HTTPServer)


def tokenize(column_name: str) -> list:
    """컬럼명을 단어 단위로 나누고 대문자로 정규화.

    구분자('_' 공백 하이픈 등)뿐 아니라 camelCase(대소문자 경계)도 분리한다.
    대소문자 경계 분리는 반드시 대문자화 '전'에 수행한다(경계 정보 보존).

    예: 'api_use_yn'  -> ['API', 'USE', 'YN']
        'bidBeginDt'  -> ['BID', 'BEGIN', 'DT']
        'HTTPServer'  -> ['HTTP', 'SERVER']
        'USERID'      -> ['USERID']   (전부 대문자는 경계 신호가 없어 그대로)
    빈 토큰은 제외한다.
    """
    if not column_name:
        return []
    s = str(column_name).strip()
    s = _ACRONYM.sub(r"\1_\2", s)     # HTTPServer -> HTTP_Server
    s = _CAMEL.sub(r"\1_\2", s)       # bidBeginDt -> bid_Begin_Dt
    parts = _SPLIT.split(s)
    return [p.upper() for p in parts if p]
