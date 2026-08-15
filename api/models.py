"""SQLModel table models persisted on Turso."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Listing(SQLModel, table=True):
    __tablename__ = "listings"

    url: str = Field(primary_key=True)
    title: str = ""
    city: str = ""
    description: str = ""
    price: float | None = None
    rating: float | None = None
    amenities: str = "[]"
    house_rules: str = "[]"
    image_url: str = ""
    image_urls: str = "[]"
    full_text: str = ""
    matched_keywords: str = "[]"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Embedding(SQLModel, table=True):
    __tablename__ = "embeddings"

    url: str = Field(primary_key=True, foreign_key="listings.url")
    vector: str
    model: str
    task_type: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
