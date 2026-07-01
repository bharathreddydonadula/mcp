# ServiceNow MCP Server

A production-quality [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes ServiceNow functionality as MCP tools, built with the official MCP Python SDK and ServiceNow REST APIs.

## Architecture

```
MCP Client
    │
FastMCP Server          (server.py)
    │
MCP Tool Layer          (tools/)
    │
Business Service Layer  (services/)
    │
Generic ServiceNow Client (client/servicenow_client.py)
    │
ServiceNow REST APIs
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A ServiceNow instance (PDI or production)

### 2. Install

```powershell
git clone <repo>
cd servicenow-mcp
uv sync
```

### 3. Configure

```powershell
cp .env.example .env
# Edit .env with your ServiceNow instance URL and credentials
```

Minimum required settings:

```env
SERVICENOW_INSTANCE_URL=https://devXXXXX.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your-password
```

### 4. Run

**stdio transport** (for Claude Desktop / Cursor):

```powershell
uv run python server.py
```

**SSE transport** (HTTP-based):

```powershell
$env:MCP_TRANSPORT="sse"
uv run python server.py
```

## Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "servicenow": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "C:\\Temp\\MCP\\servicenow-mcp",
      "env": {
        "SERVICENOW_INSTANCE_URL": "https://devXXXXX.service-now.com",
        "SERVICENOW_USERNAME": "admin",
        "SERVICENOW_PASSWORD": "your-password"
      }
    }
  }
}
```

## Available Tools

### Incident Tools

| Tool | Description |
|---|---|
| `create_incident` | Create a new incident |
| `get_incident` | Get incident by number or sys_id |
| `search_incidents` | Search with flexible filters |
| `update_incident` | Update incident fields |
| `resolve_incident` | Resolve with resolution notes |
| `add_work_note` | Add internal work note |
| `add_comment` | Add customer-visible comment |

### User Tools

| Tool | Description |
|---|---|
| `get_user` | Get user by sys_id or username |
| `search_users` | Search by name, email, department |
| `get_current_user` | Get authenticated user |

## Authentication

### Basic Auth (default)

```env
SERVICENOW_AUTH_MODE=basic
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your-password
```

### OAuth 2.0

```env
SERVICENOW_AUTH_MODE=oauth
SERVICENOW_CLIENT_ID=your-client-id
SERVICENOW_CLIENT_SECRET=your-client-secret
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your-password
```

## Running Tests

```powershell
# Unit tests only (no ServiceNow instance required)
uv run pytest tests/unit/ -v

# Integration tests (requires configured .env)
uv run pytest tests/integration/ -v

# All tests
uv run pytest -v
```

## Development

```powershell
# Lint
uv run ruff check .

# Type check
uv run mypy .

# Format
uv run ruff format .
```

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `SERVICENOW_INSTANCE_URL` | — | **Required.** Instance base URL |
| `SERVICENOW_AUTH_MODE` | `basic` | `basic` or `oauth` |
| `SERVICENOW_USERNAME` | — | Login username |
| `SERVICENOW_PASSWORD` | — | Login password |
| `SERVICENOW_CLIENT_ID` | — | OAuth client ID |
| `SERVICENOW_CLIENT_SECRET` | — | OAuth client secret |
| `SERVICENOW_TIMEOUT_SECONDS` | `30` | HTTP timeout |
| `SERVICENOW_MAX_RETRIES` | `3` | Retry attempts |
| `SERVICENOW_RETRY_BACKOFF` | `1.0` | Initial backoff (seconds) |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `MCP_SSE_HOST` | `0.0.0.0` | SSE bind host |
| `MCP_SSE_PORT` | `8000` | SSE bind port |
| `LOG_LEVEL` | `INFO` | Logging level |
