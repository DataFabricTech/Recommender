from pydantic import BaseModel
from typing import Optional, Literal, List

class ResponseModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[dict]
    
class RecommendResultModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[List]
    