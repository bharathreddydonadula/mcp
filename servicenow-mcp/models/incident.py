"""Pydantic models for ServiceNow Incident records.

These models map directly to ServiceNow Table API field names so that
service-layer code can pass them straight to the client without translation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IncidentState(str, Enum):
    """Numeric state values for the ``incident`` table."""

    NEW = "1"
    IN_PROGRESS = "2"
    ON_HOLD = "3"
    RESOLVED = "6"
    CLOSED = "7"
    CANCELLED = "8"


class IncidentPriority(str, Enum):
    """Numeric priority values for the ``incident`` table."""

    CRITICAL = "1"
    HIGH = "2"
    MODERATE = "3"
    LOW = "4"
    PLANNING = "5"


class IncidentCreate(BaseModel):
    """Fields required (and optional) when creating a new incident."""

    model_config = ConfigDict(populate_by_name=True)

    short_description: str = Field(
        ..., description="Brief summary of the incident", max_length=160
    )
    description: str | None = Field(default=None, description="Detailed description")
    caller_id: str | None = Field(
        default=None, description="sys_id of the user reporting the incident"
    )
    category: str | None = Field(default=None, description="Incident category")
    subcategory: str | None = Field(default=None, description="Incident subcategory")
    impact: str | None = Field(default=None, description="Impact: 1=High, 2=Medium, 3=Low")
    urgency: str | None = Field(default=None, description="Urgency: 1=High, 2=Medium, 3=Low")
    priority: IncidentPriority | None = Field(default=None, description="Incident priority")
    assignment_group: str | None = Field(
        default=None, description="sys_id of the assignment group"
    )
    assigned_to: str | None = Field(
        default=None, description="sys_id of the assigned user"
    )
    cmdb_ci: str | None = Field(
        default=None, description="sys_id of the configuration item"
    )

    def to_servicenow_dict(self) -> dict[str, Any]:
        """Return only non-None fields for the ServiceNow API payload."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class IncidentUpdate(BaseModel):
    """Fields that can be updated on an existing incident."""

    model_config = ConfigDict(populate_by_name=True)

    short_description: str | None = Field(default=None, max_length=160)
    description: str | None = None
    state: IncidentState | None = None
    priority: IncidentPriority | None = None
    impact: str | None = None
    urgency: str | None = None
    category: str | None = None
    subcategory: str | None = None
    assignment_group: str | None = None
    assigned_to: str | None = None
    cmdb_ci: str | None = None
    close_code: str | None = None
    close_notes: str | None = None

    def to_servicenow_dict(self) -> dict[str, Any]:
        """Return only non-None fields for the ServiceNow API payload."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class IncidentResponse(BaseModel):
    """Incident record as returned by the ServiceNow Table API."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    sys_id: str = Field(description="Unique record identifier")
    number: str = Field(description="Human-readable incident number, e.g. INC0001234")
    short_description: str = Field(description="Brief summary")
    description: str | None = Field(default=None)
    state: str = Field(description="Incident state code")
    priority: str | None = Field(default=None)
    impact: str | None = Field(default=None)
    urgency: str | None = Field(default=None)
    category: str | None = Field(default=None)
    subcategory: str | None = Field(default=None)
    assignment_group: str | None = Field(default=None)
    assigned_to: str | None = Field(default=None)
    caller_id: str | None = Field(default=None)
    cmdb_ci: str | None = Field(default=None)
    opened_at: str | None = Field(default=None)
    resolved_at: str | None = Field(default=None)
    closed_at: str | None = Field(default=None)
    close_code: str | None = Field(default=None)
    close_notes: str | None = Field(default=None)
    sys_created_on: str | None = Field(default=None)
    sys_updated_on: str | None = Field(default=None)

    @classmethod
    def from_servicenow(cls, data: dict[str, Any]) -> IncidentResponse:
        """Construct from a raw ServiceNow API record.

        ServiceNow may return reference fields as dicts with ``value`` and
        ``display_value`` keys.  This method normalises them to plain strings.
        """
        normalised: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                normalised[key] = value.get("value", "")
            else:
                normalised[key] = value
        return cls.model_validate(normalised)


class WorkNoteRequest(BaseModel):
    """Request model for adding a work note or customer-visible comment."""

    text: str = Field(..., description="Content of the work note or comment", min_length=1)
