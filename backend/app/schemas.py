from typing import Literal
from pydantic import BaseModel, Field
from src.config import DEFAULT_MODEL

class BlogRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=2000)
    length: str = Field(default="Standard · about 1,000 words", max_length=120)
    model_name: Literal["qwen3.5:4b", "qwen3:1.7b"] = DEFAULT_MODEL

class ActionRequest(BaseModel):
    action: Literal["approve", "edit", "reject"]
    platforms: list[Literal["wordpress", "devto"]] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    feedback: str = Field(default="", max_length=4000)
    text: str | None = Field(default=None, max_length=3000)


# Create the signed session cookie used by the publishing dashboard.

class LoginRequest(BaseModel):
    password: str = Field(max_length=512)

# Sign in and issue a secure dashboard session cookie.

