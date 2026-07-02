"""데이터 타입 정규화: 이질적인 원천 컬럼 타입과 표준 도메인 data_type을
계열(문자/숫자/날짜)로 묶어 비교한다.

원천 컬럼 타입은 INT, TEXT, VARCHAR2(128), NUMBER, STRING 등 DB마다 제각각이고,
표준 도메인 data_type은 VARCHAR/NUMERIC/CHAR/DATETIME 4종뿐이라 그대로 비교하면
오탐이 난다. 그래서 둘 다 계열로 정규화한 뒤 계열이 같은지로 판정한다.
(CHAR vs VARCHAR 같은 문자 내부 차이는 원천마다 표현이 달라 구분하지 않는다.)
"""

_CHAR = {
    "VARCHAR", "VARCHAR2", "NVARCHAR", "NVARCHAR2", "CHAR", "NCHAR",
    "CHARACTER", "TEXT", "STRING", "CLOB", "NCLOB", "NTEXT", "LONGTEXT",
    "MEDIUMTEXT", "TINYTEXT", "ENUM", "UUID",
}
_NUM = {
    "INT", "INTEGER", "INT2", "INT4", "INT8", "SMALLINT", "BIGINT", "TINYINT",
    "NUMBER", "NUMERIC", "DECIMAL", "DEC", "DOUBLE", "FLOAT", "REAL", "MONEY",
    "BIT", "SERIAL", "BIGSERIAL", "SMALLSERIAL",
}
_DATE = {
    "DATE", "DATETIME", "TIMESTAMP", "TIMESTAMPTZ", "TIME", "TIMETZ",
    "SMALLDATETIME", "YEAR",
}

CHAR, NUM, DATE, OTHER = "CHAR", "NUM", "DATE", "OTHER"


def normalize_type(raw_type: str) -> str:
    """원천/도메인 타입 문자열을 계열(CHAR/NUM/DATE/OTHER)로 정규화.

    'VARCHAR(100)' -> CHAR, 'NUMBER' -> NUM, 'DATETIME' -> DATE 등.
    괄호의 길이/정밀도는 떼고, 점이 있으면 마지막 토큰을 본다.
    """
    if not raw_type:
        return OTHER
    base = str(raw_type).split("(")[0].strip().upper()
    if "." in base:                       # INFORMATION_SCHEMA.SQL_IDENTIFIER 등
        base = base.split(".")[-1]
    if base in _CHAR or "CHAR" in base or "TEXT" in base or "STRING" in base:
        return CHAR
    if base in _NUM:
        return NUM
    if base in _DATE or "TIMESTAMP" in base:
        return DATE
    return OTHER


def type_matches(column_type: str, domain_data_type: str) -> bool:
    """컬럼 타입이 도메인 data_type 계열과 맞는지.

    둘 다 계열이 분명(CHAR/NUM/DATE)할 때만 엄격히 비교한다.
    한쪽이라도 OTHER(판단 불가)면 오탐 방지를 위해 통과(True) 처리한다.
    """
    c = normalize_type(column_type)
    d = normalize_type(domain_data_type)
    if c == OTHER or d == OTHER:
        return True
    return c == d


import re

_LEN_RE = re.compile(r"\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)")


def parse_length(raw_type: str):
    """컬럼 타입 문자열에서 길이/소수점 추출.
    'VARCHAR(100)'->(100,None), 'NUMERIC(5,2)'->(5,2), 'INT'->(None,None)."""
    if not raw_type:
        return (None, None)
    m = _LEN_RE.search(str(raw_type))
    if not m:
        return (None, None)
    size = int(m.group(1))
    dec = int(m.group(2)) if m.group(2) else None
    return (size, dec)


def type_check(column_type, domain_data_type, domain_size=None, domain_decimal=None):
    """계열 + 길이까지 비교. 도메인에 길이(domain_size)가 있으면 길이도 맞아야 일치.

    반환: (ok: bool, reason: None|'TYPE'|'LENGTH', detail: str)
    - 계열이 판단 불가(OTHER)면 통과.
    - 컬럼에 길이 표기가 없으면(INT/TEXT 등) 길이 비교는 생략(계열만).
    """
    c = normalize_type(column_type)
    d = normalize_type(domain_data_type)
    if c == OTHER or d == OTHER:
        return (True, None, "")
    if c != d:
        fam = {"CHAR": "문자", "NUM": "숫자", "DATE": "날짜"}
        return (False, "TYPE", f"타입 계열 불일치 ({fam.get(c, c)} ≠ 표준 {fam.get(d, d)})")
    col_size, col_dec = parse_length(column_type)
    if col_size is None or domain_size in (None, "", 0):
        return (True, None, "")
    if int(col_size) != int(domain_size):
        return (False, "LENGTH", f"길이 불일치 (컬럼 {col_size} ≠ 표준 {domain_size})")
    if domain_decimal not in (None, "", 0) and col_dec is not None and int(col_dec) != int(domain_decimal):
        return (False, "LENGTH", f"소수점 불일치 (컬럼 {col_dec} ≠ 표준 {domain_decimal})")
    return (True, None, "")
