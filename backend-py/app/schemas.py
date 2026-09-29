from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


TicketStatus = Literal["Open", "In progress", "Resolved"]
TicketPriority = Literal["Low", "Normal", "High"]
TicketCategory = Literal["Account access", "Hardware", "Software", "Network", "Other"]


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class TicketCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=120)
    category: TicketCategory | None = None
    priority: TicketPriority = "Normal"
    description: str = Field(min_length=1, max_length=3000)

    @field_validator("name", "subject", "description", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class TicketUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    status: TicketStatus = "Open"
    assignee: str | None = Field(default=None, max_length=100)
    category: TicketCategory | None = None

    @field_validator("category")
    @classmethod
    def require_category_value(cls, value: TicketCategory | None) -> TicketCategory:
        if value is None:
            raise ValueError("Category cannot be null")
        return value

    @field_validator("assignee")
    @classmethod
    def normalize_unassigned(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class TicketRead(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    id: str = Field(validation_alias="ticket_key")
    subject: str
    name: str
    email: EmailStr
    category: TicketCategory
    predicted_category: TicketCategory | None
    prediction_confidence: float | None
    category_reviewed_at: datetime | None
    category_corrected_at: datetime | None
    priority: TicketPriority
    description: str
    status: TicketStatus
    assignee: str | None
    created_at: datetime
    resolved_at: datetime | None