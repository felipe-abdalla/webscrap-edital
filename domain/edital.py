from typing import Optional
from datetime import date, datetime, timezone
from sqlmodel import SQLModel, Field


class Edital(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    title: Optional[str]
    url: str = Field(index=True, unique=True)
    content: Optional[str]

    deadline: Optional[date]

    domain: Optional[str]
    score: int
    phrase: Optional[str]

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
