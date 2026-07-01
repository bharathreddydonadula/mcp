"""MCP tool definitions for ServiceNow User operations.

Each function is a thin wrapper that delegates to :class:`~services.UserService`.
No business logic lives here.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from client.servicenow_client import ServiceNowClient
from models.user import UserSearchParams
from services.user_service import UserService

logger = logging.getLogger(__name__)


def register_user_tools(mcp: FastMCP, client: ServiceNowClient) -> None:
    """Register all user-related MCP tools on the given FastMCP server.

    Args:
        mcp: The :class:`~mcp.server.fastmcp.FastMCP` server instance.
        client: An open :class:`~client.ServiceNowClient` to inject into the service.
    """
    service = UserService(client)

    @mcp.tool(
        name="get_user",
        description=(
            "Retrieve a ServiceNow user by sys_id or exact username. "
            "Returns the full user record including contact details."
        ),
    )
    async def get_user(sys_id_or_username: str) -> dict[str, Any]:
        """Fetch a single user by sys_id or username."""
        result = await service.get_user(sys_id_or_username)
        return result.model_dump()

    @mcp.tool(
        name="search_users",
        description=(
            "Search ServiceNow users by name, username, email, or department. "
            "All parameters are optional and combined with AND logic."
        ),
    )
    async def search_users(
        name: str | None = None,
        user_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        active_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search for users matching the given criteria."""
        params = UserSearchParams(
            name=name,
            user_name=user_name,
            email=email,
            department=department,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        results = await service.search_users(params)
        return [r.model_dump() for r in results]

    @mcp.tool(
        name="get_current_user",
        description=(
            "Retrieve the currently authenticated ServiceNow user. "
            "Returns the user associated with the configured credentials."
        ),
    )
    async def get_current_user() -> dict[str, Any]:
        """Fetch the currently authenticated user."""
        result = await service.get_current_user()
        return result.model_dump()
