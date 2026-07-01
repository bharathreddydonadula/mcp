"""Integration tests for ServiceNowClient against a real PDI instance."""

from __future__ import annotations

import pytest

from client.query_builder import QueryBuilder
from client.servicenow_client import ServiceNowClient
from tests.integration.conftest import skip_without_pdi


@skip_without_pdi
class TestClientIntegration:
    """Live CRUD tests against the configured ServiceNow PDI."""

    async def test_list_incidents_returns_results(
        self, integration_client: ServiceNowClient
    ) -> None:
        params = QueryBuilder().limit(5).fields(["sys_id", "number"]).build()
        records = await integration_client.list_records("incident", params=params)
        assert isinstance(records, list)

    async def test_create_and_delete_record(
        self, integration_client: ServiceNowClient
    ) -> None:
        created = await integration_client.create_record(
            "incident",
            {"short_description": "MCP integration test — safe to delete"},
        )
        sys_id = created["sys_id"]
        assert sys_id

        retrieved = await integration_client.get_record("incident", sys_id)
        assert retrieved["sys_id"] == sys_id

        await integration_client.delete_record("incident", sys_id)

    async def test_update_record(
        self, integration_client: ServiceNowClient
    ) -> None:
        created = await integration_client.create_record(
            "incident",
            {"short_description": "MCP integration test — update test"},
        )
        sys_id = created["sys_id"]

        updated = await integration_client.update_record(
            "incident", sys_id, {"description": "Updated by integration test"}
        )
        assert updated["sys_id"] == sys_id

        await integration_client.delete_record("incident", sys_id)
