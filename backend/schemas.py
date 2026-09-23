"""Pydantic request/response models for the API."""

from typing import List, Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    source_documents: List[str]
    conversation_id: str
    message_id: str
    hit_cap: bool
