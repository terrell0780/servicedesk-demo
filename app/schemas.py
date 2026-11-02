"""Request/response models."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v.lower()


class JobIn(BaseModel):
    client_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    price_cents: int = Field(ge=0, le=100_000_000)


class JobStatusIn(BaseModel):
    status: str = Field(pattern="^(open|done)$")


class InvoiceIn(BaseModel):
    job_id: int = Field(gt=0)
    amount_cents: int = Field(ge=0, le=100_000_000)


class InvoiceStatusIn(BaseModel):
    status: str = Field(pattern="^(draft|sent|paid)$")
