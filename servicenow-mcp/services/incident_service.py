"""Business service layer for ServiceNow Incident records.

This module is entirely MCP-agnostic.  It depends only on the generic
:class:`~client.ServiceNowClient` and the domain models in ``models.incident``.

All public methods are ``async`` because the underlying HTTP client is async.
"""

from __future__ import annotations

import logging
from typing import Any

from client.query_builder import QueryBuilder
from client.servicenow_client import ServiceNowClient
from exceptions.servicenow_exceptions import RecordNotFoundError, ServiceNowValidationError
from models.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentState,
    IncidentUpdate,
    WorkNoteRequest,
)

logger = logging.getLogger(__name__)

_INCIDENT_TABLE = "incident"
_INCIDENT_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "priority",
    "impact",
    "urgency",
    "category",
    "subcategory",
    "assignment_group",
    "assigned_to",
    "caller_id",
    "cmdb_ci",
    "opened_at",
    "resolved_at",
    "closed_at",
    "close_code",
    "close_notes",
    "sys_created_on",
    "sys_updated_on",
]


class IncidentService:
    """Provides business operations on ServiceNow Incident records.

    Args:
        client: An open :class:`~client.ServiceNowClient` instance.
    """

    def __init__(self, client: ServiceNowClient) -> None:
        self._client = client

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _resolve_sys_id(self, number_or_sys_id: str) -> str:
        """Resolve an incident number (e.g. INC0001234) to its sys_id.

        If the input looks like a sys_id (32 hex chars, no prefix) it is
        returned unchanged.  Otherwise a lookup by ``number`` is performed.

        Args:
            number_or_sys_id: Either an incident number or a sys_id.

        Returns:
            The sys_id of the incident.

        Raises:
            RecordNotFoundError: If no incident with that number exists.
        """
        if len(number_or_sys_id) == 32 and number_or_sys_id.startswith(
            tuple("0123456789abcdef")
        ):
            return number_or_sys_id

        params = (
            QueryBuilder()
            .equals("number", number_or_sys_id)
            .fields(["sys_id"])
            .limit(1)
            .build()
        )
        records = await self._client.list_records(_INCIDENT_TABLE, params=params)
        if not records:
            raise RecordNotFoundError(
                table=_INCIDENT_TABLE, identifier=number_or_sys_id
            )
        return str(records[0]["sys_id"])

    @staticmethod
    def _default_params() -> dict[str, str]:
        """Return default query parameters used by most read operations."""
        return QueryBuilder().fields(_INCIDENT_FIELDS).build()

    # ── CRUD operations ───────────────────────────────────────────────────────

    async def create_incident(self, data: IncidentCreate) -> IncidentResponse:
        """Create a new incident.

        Args:
            data: Validated :class:`~models.IncidentCreate` payload.

        Returns:
            The newly created incident as an :class:`~models.IncidentResponse`.
        """
        logger.info("Creating incident: %s", data.short_description)
        payload = data.to_servicenow_dict()
        raw = await self._client.create_record(_INCIDENT_TABLE, payload)
        return IncidentResponse.from_servicenow(raw)

    async def get_incident(self, number_or_sys_id: str) -> IncidentResponse:
        """Retrieve a single incident by number or sys_id.

        Args:
            number_or_sys_id: Incident number (e.g. ``"INC0001234"``) or sys_id.

        Returns:
            The incident record.

        Raises:
            RecordNotFoundError: If the incident does not exist.
        """
        sys_id = await self._resolve_sys_id(number_or_sys_id)
        raw = await self._client.get_record(
            _INCIDENT_TABLE, sys_id, params=self._default_params()
        )
        return IncidentResponse.from_servicenow(raw)

    async def search_incidents(
        self,
        *,
        query: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        assigned_to: str | None = None,
        assignment_group: str | None = None,
        caller_id: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[IncidentResponse]:
        """Search incidents using flexible criteria.

        All parameters are optional and combined with AND logic.

        Args:
            query: Free-text encoded query appended verbatim (advanced use).
            state: Filter by state code (see :class:`~models.IncidentState`).
            priority: Filter by priority code.
            assigned_to: Filter by assigned user sys_id.
            assignment_group: Filter by assignment group sys_id.
            caller_id: Filter by caller sys_id.
            category: Filter by category.
            limit: Maximum records to return.
            offset: Zero-based record offset for pagination.

        Returns:
            List of matching incidents.
        """
        qb = QueryBuilder()

        if state:
            qb.equals("state", state)
        if priority:
            qb.equals("priority", priority)
        if assigned_to:
            qb.equals("assigned_to", assigned_to)
        if assignment_group:
            qb.equals("assignment_group", assignment_group)
        if caller_id:
            qb.equals("caller_id", caller_id)
        if category:
            qb.equals("category", category)
        if query:
            qb._conditions.append(query)  # noqa: SLF001

        params = (
            qb.fields(_INCIDENT_FIELDS)
            .limit(limit)
            .offset(offset)
            .order_by("sys_created_on", descending=True)
            .build()
        )

        records = await self._client.list_records(_INCIDENT_TABLE, params=params)
        return [IncidentResponse.from_servicenow(r) for r in records]

    async def update_incident(
        self, number_or_sys_id: str, data: IncidentUpdate
    ) -> IncidentResponse:
        """Partially update an existing incident.

        Args:
            number_or_sys_id: Incident number or sys_id.
            data: Fields to update.

        Returns:
            The updated incident record.
        """
        sys_id = await self._resolve_sys_id(number_or_sys_id)
        payload = data.to_servicenow_dict()
        if not payload:
            raise ServiceNowValidationError("No fields provided for update.")
        raw = await self._client.update_record(_INCIDENT_TABLE, sys_id, payload)
        return IncidentResponse.from_servicenow(raw)

    async def resolve_incident(
        self,
        number_or_sys_id: str,
        resolution_notes: str,
        *,
        close_code: str = "Solved (Permanently)",
    ) -> IncidentResponse:
        """Resolve an incident.

        Sets the state to ``RESOLVED`` and records the resolution notes and code.

        Args:
            number_or_sys_id: Incident number or sys_id.
            resolution_notes: Description of how the incident was resolved.
            close_code: ServiceNow close code (default: ``"Solved (Permanently)"``).

        Returns:
            The resolved incident record.
        """
        logger.info("Resolving incident %s", number_or_sys_id)
        update = IncidentUpdate(
            state=IncidentState.RESOLVED,
            close_notes=resolution_notes,
            close_code=close_code,
        )
        return await self.update_incident(number_or_sys_id, update)

    # ── Journal entries ───────────────────────────────────────────────────────

    async def add_work_note(
        self, number_or_sys_id: str, request: WorkNoteRequest
    ) -> dict[str, Any]:
        """Add a work note (internal) to an incident.

        Work notes are only visible to agents, not to end users.

        Args:
            number_or_sys_id: Incident number or sys_id.
            request: The work note text.

        Returns:
            The updated record summary returned by ServiceNow.
        """
        sys_id = await self._resolve_sys_id(number_or_sys_id)
        logger.info("Adding work note to incident %s", sys_id)
        return await self._client.update_record(
            _INCIDENT_TABLE,
            sys_id,
            {"work_notes": request.text},
        )

    async def add_comment(
        self, number_or_sys_id: str, request: WorkNoteRequest
    ) -> dict[str, Any]:
        """Add a customer-visible comment to an incident.

        Comments are visible to the caller/end user in the portal.

        Args:
            number_or_sys_id: Incident number or sys_id.
            request: The comment text.

        Returns:
            The updated record summary returned by ServiceNow.
        """
        sys_id = await self._resolve_sys_id(number_or_sys_id)
        logger.info("Adding comment to incident %s", sys_id)
        return await self._client.update_record(
            _INCIDENT_TABLE,
            sys_id,
            {"comments": request.text},
        )
