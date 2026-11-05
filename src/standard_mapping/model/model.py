from pydantic import BaseModel
from typing import Optional


class ResponseModel(BaseModel):
    status_code: Optional[int] = None
    result: Optional[dict]
