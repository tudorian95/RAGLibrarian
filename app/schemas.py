# app/schemas.py
from typing import List, Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    prompt: str

class RetrievedDoc(BaseModel):
    title: str
    author: Optional[str] = None
    themes: List[str] = []
    score: Optional[float] = None

class ChatResponse(BaseModel):
    message: str
    recommendation_title: Optional[str] = None
    summary: Optional[str] = None
    sources: List[RetrievedDoc] = []
