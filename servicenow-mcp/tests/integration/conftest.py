"""Integration test configuration.

Integration tests are automatically skipped when SERVICENOW_INSTANCE_URL
is not set in the environment.  To run them, export your PDI credentials::

    $env:SERVICENOW_INSTANCE_URL="https://devXXXXX.service-now.com"
    $env:SERVICENOW_USERNAME="admin"
    $env:SERVICENOW_PASSWORD="your-password"
    uv run pytest tests/integration/ -v
"""

from __future__ import annotations

import os

import pytest

from client.servicenow_client import ServiceNowClient
from config import get_settings


def _pdi_available() -> bool:
    return bool(os.environ.get("SERVICENOW_INSTANCE_URL"))


skip_without_pdi = pytest.mark.skipif(
    not _pdi_available(),
    reason="SERVICENOW_INSTANCE_URL not set — skipping integration tests",
)


@pytest.fixture(scope="session")
async def integration_client() -> ServiceNowClient:
    """A real ServiceNowClient connected to the configured PDI instance."""
    client = ServiceNowClient.from_settings(get_settings())
    await client._open()
    return client
