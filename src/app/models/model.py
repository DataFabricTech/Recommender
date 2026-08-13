from pydantic import BaseModel
from typing import Optional, Literal, List

class ResponseModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[dict]
    
class RecommendResultModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[List]


class FusionJoinKeyModel(BaseModel):
    left: str
    right: str
    type_match: Optional[bool] = None
    value_overlap: Optional[float] = None
    cardinality: str
    confidence: float
    name_score: Optional[float] = None
    semantic_score: Optional[float] = None
    known: bool = False


class FusionRecommendItemModel(BaseModel):
    meta_id: str
    meta_name: str
    system_id: Optional[str] = None
    score: float
    join_keys: List[FusionJoinKeyModel] = []
    reason: Optional[str] = None


class FusionRecommendResultModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[List[FusionRecommendItemModel]]


class SimilarAttrMatchModel(BaseModel):
    """탐지된 유사 속성 한 쌍."""
    left: str
    right: str
    score: float
    margin: float


class SimilarAttrDictionaryModel(BaseModel):
    """탐지에 사용한 임베딩 사전. 어떤 사전을 썼는지 응답으로 밝힌다."""
    file: str
    sha256: Optional[str] = None
    names: int = 0
    dim: int = 0
    model: Optional[str] = None


class SimilarAttrDetectResultModel(BaseModel):
    left_table: str
    right_table: str
    left_columns: int
    right_columns: int
    excluded_left: List[str] = []
    excluded_right: List[str] = []
    params: dict = {}
    dictionary: Optional[SimilarAttrDictionaryModel] = None
    matches: List[SimilarAttrMatchModel] = []


class SimilarAttrDetectResponseModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[SimilarAttrDetectResultModel] = None
