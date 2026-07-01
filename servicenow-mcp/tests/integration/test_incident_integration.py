"""Integration tests for IncidentService against a real PDI instance."""

from __future__ import annotations

import pytest

from client.servicenow_client import ServiceNowClient
from models.incident import IncidentCreate, IncidentUpdate, WorkNoteRequest
from services.incident_service import IncidentService
from tests.integration.conftest import skip_without_pdi


@skip_without_pdi
class TestIncidentServiceIntegration:
    """Live incident service tests against the configured ServiceNow PDI."""

    @pytest.fixture()
    def incident_service(self, integration_client: ServiceNowClient) -> IncidentService:
        return IncidentService(integration_client)

    async def test_create_and_get_incident(
        self, incident_service: IncidentService
    ) -> None:
        data = IncidentCreate(
            short_description="MCP integration test incident — safe to delete",
            category="software",
        )
        created = await incident_service.create_incident(data)
        assert created.number.startswith("INC")

        fetched = await incident_service.get_incident(created.number)
        assert fetched.sys_id == created.sys_id

        await incident_service._client.delete_record("incident", created.sys_id)

    async def test_search_incidents(
        self, incident_service: IncidentService
    ) -> None:
        results = await incident_service.search_incidents(limit=5)
        assert isinstance(results, list)

    async def test_add_work_note(
        self, incident_service: IncidentService
    ) -> None:
        data = IncidentCreate(short_description="MCP work note test — safe to delete")
        created = await incident_service.create_incident(data)

        request = WorkNoteRequest(text="Integration test work note")
        await incident_service.add_work_note(created.sys_id, request)

        await incident_service._client.delete_record("incident", created.sys_id)

    async def test_resolve_incident(
        self, incident_service: IncidentService
    ) -> None:
        data = IncidentCreate(short_description="MCP resolve test — safe to delete")
        created = await incident_service.create_incident(data)

        resolved = await incident_service.resolve_incident(
            created.sys_id,
            resolution_notes="Resolved by integration test",
        )
        assert resolved.state == "6"

        await incident_service._client.delete_record("incident", created.sys_id)
