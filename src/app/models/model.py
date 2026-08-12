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
