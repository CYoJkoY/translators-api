from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = Field(default="auto", min_length=1, max_length=32)
    target: str = Field(default="en", min_length=1, max_length=32)
    translator: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    source: str = Field(default="auto", min_length=1, max_length=32)
    target: str = Field(default="en", min_length=1, max_length=32)
    translator: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("texts")
    @classmethod
    def reject_blank_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("texts must not contain blank values")
        return values


class HtmlTranslateRequest(BaseModel):
    html: str = Field(min_length=1)
    source: str = Field(default="auto", min_length=1, max_length=32)
    target: str = Field(default="en", min_length=1, max_length=32)
    translator: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("html")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("html must not be blank")
        return value


class TranslateResponse(BaseModel):
    text: str
    translation: str
    source: str
    target: str
    translator: str
    fallback: bool = False
    request_id: str


class BatchItem(BaseModel):
    text: str
    translation: str | None
    index: int
    status: Literal["success", "error"] = "success"
    error_code: str | None = None
    error_message: str | None = None


class BatchTranslateResponse(BaseModel):
    items: list[BatchItem]
    source: str
    target: str
    translator: str
    fallback: bool = False
    completed: int
    failed: int
    partial_success: bool
    deadline_exceeded: bool = False
    request_id: str


class HtmlTranslateResponse(BaseModel):
    html: str
    translation: str
    source: str
    target: str
    translator: str
    fallback: bool = False
    request_id: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
