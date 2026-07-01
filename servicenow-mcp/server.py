"""ServiceNow MCP Server entrypoint.

Starts a FastMCP server with all registered tools and supports both
stdio (default) and SSE transports, controlled by the ``MCP_TRANSPORT``
environment variable.

Usage (stdio)::

    uv run python server.py

Usage (SSE)::

    MCP_TRANSPORT=sse uv run python server.py
"""

from __future__ import annotations

import asyncio
import logging
import sys

from mcp.server.fastmcp import FastMCP

from config import MCPTransport, configure_logging, get_settings
from exceptions.servicenow_exceptions import ServiceNowError
from client.servicenow_client import ServiceNowClient
from tools.incident_tools import register_incident_tools
from tools.user_tools import register_user_tools

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="servicenow-mcp",
    instructions=(
        "ServiceNow MCP Server. Use the available tools to manage incidents, "
        "users, and other ServiceNow records. "
        "Authenticate via the credentials configured in your .env file."
    ),
)


async def _build_server() -> None:
    """Initialise services and register all MCP tools."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "Initialising ServiceNow MCP Server (transport=%s, instance=%s)",
        settings.mcp_transport.value,
        settings.instance_url,
    )

    client = ServiceNowClient.from_settings(settings)
    await client._open()  # noqa: SLF001

    register_incident_tools(mcp, client)
    register_user_tools(mcp, client)

    logger.info("All tools registered. Server ready.")


def main() -> None:
    """Entrypoint: resolve transport and start the MCP server."""
    settings = get_settings()
    configure_logging(settings.log_level)

    asyncio.run(_build_server())

    if settings.mcp_transport == MCPTransport.SSE:
        logger.info(
            "Starting SSE transport on %s:%d",
            settings.mcp_sse_host,
            settings.mcp_sse_port,
        )
        mcp.run(
            transport="sse",
            host=settings.mcp_sse_host,
            port=settings.mcp_sse_port,
        )
    else:
        logger.info("Starting stdio transport")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    try:
        main()
    except ServiceNowError as exc:
        logger.critical("ServiceNow error during startup: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.critical("Unexpected error during startup: %s", exc, exc_info=True)
        sys.exit(1)
