"""Unit tests for IncidentService using mocked ServiceNowClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.servicenow_exceptions import RecordNotFoundError, ServiceNowValidationError
from models.incident import IncidentCreate, IncidentPriority, IncidentUpdate, WorkNoteRequest
from services.incident_service import IncidentService


def _make_incident_raw(
    sys_id: str = "abc123",
    number: str = "INC0001234",
    state: str = "1",
) -> dict[str, str]:
    return {
        "sys_id": sys_id,
        "number": number,
        "short_description": "Test incident",
        "description": "Detailed description",
        "state": state,
        "priority": "3",
        "impact": "2",
        "urgency": "2",
        "category": "software",
        "subcategory": "",
        "assignment_group": "",
        "assigned_to": "",
        "caller_id": "",
        "cmdb_ci": "",
        "opened_at": "2024-01-01 10:00:00",
        "resolved_at": "",
        "closed_at": "",
        "close_code": "",
        "close_notes": "",
        "sys_created_on": "2024-01-01 10:00:00",
        "sys_updated_on": "2024-01-01 10:00:00",
    }


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    client.create_record = AsyncMock()
    client.get_record = AsyncMock()
    client.list_records = AsyncMock()
    client.update_record = AsyncMock()
    client.delete_record = AsyncMock()
    return client


@pytest.fixture()
def service(mock_client: MagicMock) -> IncidentService:
    return IncidentService(mock_client)


class TestCreateIncident:
    async def test_create_returns_incident_response(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.create_record.return_value = _make_incident_raw()
        data = IncidentCreate(short_description="Test incident")
        result = await service.create_incident(data)
        assert result.number == "INC0001234"
        assert result.sys_id == "abc123"
        mock_client.create_record.assert_awaited_once()

    async def test_create_passes_correct_table(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.create_record.return_value = _make_incident_raw()
        data = IncidentCreate(short_description="Disk full")
        await service.create_incident(data)
        call_args = mock_client.create_record.call_args
        assert call_args[0][0] == "incident"

    async def test_create_with_all_fields(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.create_record.return_value = _make_incident_raw()
        data = IncidentCreate(
            short_description="Disk full",
            description="The disk on server X is full",
            category="hardware",
            priority=IncidentPriority.HIGH,
            impact="1",
            urgency="1",
        )
        result = await service.create_incident(data)
        assert result.number == "INC0001234"
        payload = mock_client.create_record.call_args[0][1]
        assert payload["short_description"] == "Disk full"
        assert payload["priority"] == IncidentPriority.HIGH


class TestGetIncident:
    async def test_get_by_sys_id(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        mock_client.get_record.return_value = _make_incident_raw(sys_id=sys_id)
        result = await service.get_incident(sys_id)
        assert result.sys_id == sys_id
        mock_client.get_record.assert_awaited_once()

    async def test_get_by_number_resolves_to_sys_id(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = [{"sys_id": "abc123"}]
        mock_client.get_record.return_value = _make_incident_raw()
        result = await service.get_incident("INC0001234")
        assert result.sys_id == "abc123"
        mock_client.list_records.assert_awaited_once()
        mock_client.get_record.assert_awaited_once_with(
            "incident", "abc123", params=service._default_params()
        )

    async def test_get_by_number_not_found_raises(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        with pytest.raises(RecordNotFoundError) as exc_info:
            await service.get_incident("INC9999999")
        assert exc_info.value.identifier == "INC9999999"


class TestSearchIncidents:
    async def test_search_returns_list(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = [
            _make_incident_raw(sys_id="a1", number="INC0001"),
            _make_incident_raw(sys_id="a2", number="INC0002"),
        ]
        results = await service.search_incidents(state="1")
        assert len(results) == 2
        assert results[0].number == "INC0001"

    async def test_search_with_no_filters(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        results = await service.search_incidents()
        assert results == []
        mock_client.list_records.assert_awaited_once()

    async def test_search_builds_correct_query(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        await service.search_incidents(state="1", priority="2")
        call_params = mock_client.list_records.call_args[1]["params"]
        assert "state=1" in call_params["sysparm_query"]
        assert "priority=2" in call_params["sysparm_query"]


class TestUpdateIncident:
    async def test_update_returns_updated_record(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        mock_client.update_record.return_value = _make_incident_raw(sys_id=sys_id, state="2")
        data = IncidentUpdate(state="2")  # type: ignore[arg-type]
        result = await service.update_incident(sys_id, data)
        assert result.state == "2"

    async def test_update_empty_fields_raises_validation_error(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        data = IncidentUpdate()
        with pytest.raises(ServiceNowValidationError):
            await service.update_incident(sys_id, data)


class TestResolveIncident:
    async def test_resolve_sets_state_to_resolved(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        mock_client.update_record.return_value = _make_incident_raw(sys_id=sys_id, state="6")
        result = await service.resolve_incident(sys_id, "Fixed by restarting service")
        assert result.state == "6"
        payload = mock_client.update_record.call_args[0][2]
        assert payload["state"] == "6"
        assert payload["close_notes"] == "Fixed by restarting service"


class TestAddWorkNote:
    async def test_add_work_note_calls_update(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        mock_client.update_record.return_value = {"sys_id": sys_id}
        request = WorkNoteRequest(text="Investigating disk issue")
        await service.add_work_note(sys_id, request)
        payload = mock_client.update_record.call_args[0][2]
        assert payload == {"work_notes": "Investigating disk issue"}


class TestAddComment:
    async def test_add_comment_calls_update(
        self, service: IncidentService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        mock_client.update_record.return_value = {"sys_id": sys_id}
        request = WorkNoteRequest(text="We are working on your issue")
        await service.add_comment(sys_id, request)
        payload = mock_client.update_record.call_args[0][2]
        assert payload == {"comments": "We are working on your issue"}
