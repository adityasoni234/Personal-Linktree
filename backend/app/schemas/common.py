"""Shared response envelopes and pagination primitives."""

from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Success(BaseModel, Generic[T]):
    """Uniform success envelope, mirroring the error envelope in `core.errors`."""

    success: Literal[True] = True
    data: T


class Message(BaseModel):
    success: Literal[True] = True
    message: str


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
    has_next: bool
    has_previous: bool


class Page(BaseModel, Generic[T]):
    success: Literal[True] = True
    data: list[T]
    meta: PageMeta


class Pagination(BaseModel):
    """Query parameters for every collection endpoint.

    The limit is clamped server-side — `?limit=9999999` yields `MAX_PAGE_SIZE`,
    never an unbounded query.
    """

    page: int = 1
    limit: int = settings.DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def pagination_params(
    page: Annotated[int, Query(ge=1, le=10_000, description="1-based page number")] = 1,
    limit: Annotated[
        int,
        Query(ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page"),
    ] = settings.DEFAULT_PAGE_SIZE,
) -> Pagination:
    return Pagination(page=page, limit=min(limit, settings.MAX_PAGE_SIZE))


def build_page(items: list[T], total: int, pagination: Pagination) -> Page[T]:
    pages = max(1, -(-total // pagination.limit))
    return Page[T](
        data=items,
        meta=PageMeta(
            page=pagination.page,
            limit=pagination.limit,
            total=total,
            pages=pages,
            has_next=pagination.page < pages,
            has_previous=pagination.page > 1,
        ),
    )


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Documented shape of every non-2xx response."""

    success: Literal[False] = False
    error: ErrorDetail


class ReorderItem(BaseModel):
    id: str = Field(description="Resource id")
    position: int = Field(ge=0, le=10_000)


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(min_length=1, max_length=settings.MAX_PAGE_SIZE)
