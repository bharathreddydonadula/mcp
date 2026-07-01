# MCP Servers

A monorepo of production-quality [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers, sharing a single Python environment via [uv workspaces](https://docs.astral.sh/uv/concepts/workspaces/).

## Servers

| Server | Description | Status |
|---|---|---|
| [`servicenow-mcp`](./servicenow-mcp/README.md) | Manage incidents, users, and records via the ServiceNow REST API | ✅ Active |

## Workspace Structure

```
MCP/
├── pyproject.toml       # Workspace root — shared dev deps, ruff, mypy config
├── .python-version      # Python 3.12
├── .gitignore
├── uv.lock              # Single lock file for all servers
├── .venv/               # Single shared virtual environment
│
└── servicenow-mcp/      # ServiceNow MCP server
```

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### Install all dependencies

```bash
uv sync
```

### Run a server

```bash
# ServiceNow (stdio)
uv run python servicenow-mcp/server.py
```

## Adding a New Server

1. Scaffold the project:
   ```bash
   uv init my-new-mcp
   ```
2. Add it to the workspace in the root `pyproject.toml`:
   ```toml
   [tool.uv.workspace]
   members = ["servicenow-mcp", "my-new-mcp"]
   ```
3. Sync:
   ```bash
   uv sync
   ```

## Shared Tooling

All servers share the same dev toolchain, configured in the root `pyproject.toml`:

| Tool | Purpose |
|---|---|
| `ruff` | Linting and formatting |
| `mypy` | Static type checking |
| `pytest` | Unit and integration testing |
