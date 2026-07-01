"""MCP tool definitions for ServiceNow Incident operations.

Each function is a thin wrapper that:
1. Validates tool inputs via Pydantic models.
2. Delegates entirely to :class:`~services.IncidentService`.
3. Returns a structured response.

No business logic lives here.  All error handling for ServiceNow exceptions
is centralised in the server entrypoint (server.py).
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from client.servicenow_client import ServiceNowClient
from models.incident import IncidentCreate, IncidentUpdate, WorkNoteRequest
from services.incident_service import IncidentService

logger = logging.getLogger(__name__)


def register_incident_tools(mcp: FastMCP, client: ServiceNowClient) -> None:
    """Register all incident-related MCP tools on the given FastMCP server.

    Args:
        mcp: The :class:`~mcp.server.fastmcp.FastMCP` server instance.
        client: An open :class:`~client.ServiceNowClient` to inject into the service.
    """
    service = IncidentService(client)

    @mcp.tool(
        name="create_incident",
        description=(
            "Create a new ServiceNow incident. "
            "Returns the created incident record including its number and sys_id."
        ),
    )
    async def create_incident(
        short_description: str,
        description: str | None = None,
        caller_id: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        impact: str | None = None,
        urgency: str | None = None,
        priority: str | None = None,
        assignment_group: str | None = None,
        assigned_to: str | None = None,
        cmdb_ci: str | None = None,
    ) -> dict[str, Any]:
        """Create a new incident in ServiceNow."""
        data = IncidentCreate(
            short_description=short_description,
            description=description,
            caller_id=caller_id,
            category=category,
            subcategory=subcategory,
            impact=impact,
            urgency=urgency,
            priority=priority,  # type: ignore[arg-type]
            assignment_group=assignment_group,
            assigned_to=assigned_to,
            cmdb_ci=cmdb_ci,
        )
        result = await service.create_incident(data)
        return result.model_dump()

    @mcp.tool(
        name="get_incident",
        description=(
            "Retrieve a ServiceNow incident by number (e.g. INC0001234) or sys_id. "
            "Returns the full incident record."
        ),
    )
    async def get_incident(number_or_sys_id: str) -> dict[str, Any]:
        """Fetch a single incident by number or sys_id."""
        result = await service.get_incident(number_or_sys_id)
        return result.model_dump()

    @mcp.tool(
        name="search_incidents",
        description=(
            "Search ServiceNow incidents with optional filters. "
            "All parameters are optional and combined with AND logic."
        ),
    )
    async def search_incidents(
        query: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        assigned_to: str | None = None,
        assignment_group: str | None = None,
        caller_id: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search incidents by various criteria."""
        results = await service.search_incidents(
            query=query,
            state=state,
            priority=priority,
            assigned_to=assigned_to,
            assignment_group=assignment_group,
            caller_id=caller_id,
            category=category,
            limit=limit,
            offset=offset,
        )
        return [r.model_dump() for r in results]

    @mcp.tool(
        name="update_incident",
        description=(
            "Update fields on an existing ServiceNow incident. "
            "Accepts incident number or sys_id. Only provided fields are updated."
        ),
    )
    async def update_incident(
        number_or_sys_id: str,
        short_description: str | None = None,
        description: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        impact: str | None = None,
        urgency: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        assignment_group: str | None = None,
        assigned_to: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing incident."""
        data = IncidentUpdate(
            short_description=short_description,
            description=description,
            state=state,  # type: ignore[arg-type]
            priority=priority,  # type: ignore[arg-type]
            impact=impact,
            urgency=urgency,
            category=category,
            subcategory=subcategory,
            assignment_group=assignment_group,
            assigned_to=assigned_to,
        )
        result = await service.update_incident(number_or_sys_id, data)
        return result.model_dump()

    @mcp.tool(
        name="resolve_incident",
        description=(
            "Resolve a ServiceNow incident. "
            "Sets state to Resolved and records resolution notes."
        ),
    )
    async def resolve_incident(
        number_or_sys_id: str,
        resolution_notes: str,
        close_code: str = "Solved (Permanently)",
    ) -> dict[str, Any]:
        """Resolve an incident with resolution notes."""
        result = await service.resolve_incident(
            number_or_sys_id, resolution_notes, close_code=close_code
        )
        return result.model_dump()

    @mcp.tool(
        name="add_work_note",
        description=(
            "Add an internal work note to a ServiceNow incident. "
            "Work notes are only visible to agents, not end users."
        ),
    )
    async def add_work_note(number_or_sys_id: str, text: str) -> dict[str, Any]:
        """Add a work note to an incident."""
        request = WorkNoteRequest(text=text)
        return await service.add_work_note(number_or_sys_id, request)

    @mcp.tool(
        name="add_comment",
        description=(
            "Add a customer-visible comment to a ServiceNow incident. "
            "Comments are visible to the end user in the portal."
        ),
    )
    async def add_comment(number_or_sys_id: str, text: str) -> dict[str, Any]:
        """Add a public comment to an incident."""
        request = WorkNoteRequest(text=text)
        return await service.add_comment(number_or_sys_id, request)
