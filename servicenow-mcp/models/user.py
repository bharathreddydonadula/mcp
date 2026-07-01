"""Pydantic models for ServiceNow User (sys_user) records."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    """User record as returned by the ServiceNow Table API."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    sys_id: str = Field(description="Unique record identifier")
    user_name: str = Field(description="Login username")
    name: str = Field(description="Display name (first + last)")
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    mobile_phone: str | None = Field(default=None)
    department: str | None = Field(default=None)
    title: str | None = Field(default=None)
    manager: str | None = Field(default=None)
    active: str | None = Field(default=None, description="'true' or 'false'")
    sys_created_on: str | None = Field(default=None)
    sys_updated_on: str | None = Field(default=None)

    @classmethod
    def from_servicenow(cls, data: dict[str, Any]) -> UserResponse:
        """Construct from a raw ServiceNow API record.

        Normalises reference fields (dicts with ``value``/``display_value``)
        to plain strings.
        """
        normalised: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                normalised[key] = value.get("value", "")
            else:
                normalised[key] = value
        return cls.model_validate(normalised)


class UserSearchParams(BaseModel):
    """Parameters for searching users."""

    name: str | None = Field(default=None, description="Partial match on display name")
    user_name: str | None = Field(default=None, description="Exact or partial username match")
    email: str | None = Field(default=None, description="Partial match on email address")
    department: str | None = Field(default=None, description="Exact department name or sys_id")
    active_only: bool = Field(default=True, description="Return only active users")
    limit: int = Field(default=20, gt=0, le=1000, description="Maximum records to return")
    offset: int = Field(default=0, ge=0, description="Zero-based record offset")
