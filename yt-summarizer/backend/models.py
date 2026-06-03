from pydantic import BaseModel
from typing import Literal

class SummarizeRequest(BaseModel):
    url: str
    language: Literal['en', 'ar'] = 'en'