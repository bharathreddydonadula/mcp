"""Unit tests for UserService using mocked ServiceNowClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.servicenow_exceptions import RecordNotFoundError
from models.user import UserSearchParams
from services.user_service import UserService


def _make_user_raw(
    sys_id: str = "usr123",
    user_name: str = "jdoe",
    name: str = "John Doe",
) -> dict[str, str]:
    return {
        "sys_id": sys_id,
        "user_name": user_name,
        "name": name,
        "first_name": "John",
        "last_name": "Doe",
        "email": "jdoe@example.com",
        "phone": "+1-555-0100",
        "mobile_phone": "",
        "department": "IT",
        "title": "Engineer",
        "manager": "",
        "active": "true",
        "sys_created_on": "2024-01-01 10:00:00",
        "sys_updated_on": "2024-01-01 10:00:00",
    }


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    client.get_record = AsyncMock()
    client.list_records = AsyncMock()
    client._request = AsyncMock()
    return client


@pytest.fixture()
def service(mock_client: MagicMock) -> UserService:
    return UserService(mock_client)


class TestGetUser:
    async def test_get_user_by_sys_id(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        sys_id = "a" * 32
        mock_client.get_record.return_value = _make_user_raw(sys_id=sys_id)
        result = await service.get_user(sys_id)
        assert result.sys_id == sys_id
        mock_client.get_record.assert_awaited_once()

    async def test_get_user_by_username(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = [_make_user_raw()]
        result = await service.get_user("jdoe")
        assert result.user_name == "jdoe"
        mock_client.list_records.assert_awaited_once()

    async def test_get_user_username_not_found_raises(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        with pytest.raises(RecordNotFoundError) as exc_info:
            await service.get_user("nobody")
        assert exc_info.value.identifier == "nobody"

    async def test_get_user_by_sys_id_uses_get_record(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        sys_id = "b" * 32
        mock_client.get_record.return_value = _make_user_raw(sys_id=sys_id)
        await service.get_user(sys_id)
        mock_client.get_record.assert_awaited_once_with(
            "sys_user", sys_id, params=service._default_params()
        )


class TestSearchUsers:
    async def test_search_by_name(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = [_make_user_raw()]
        params = UserSearchParams(name="John")
        results = await service.search_users(params)
        assert len(results) == 1
        assert results[0].name == "John Doe"

    async def test_search_active_only_adds_filter(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        params = UserSearchParams(active_only=True)
        await service.search_users(params)
        call_params = mock_client.list_records.call_args[1]["params"]
        assert "active=true" in call_params.get("sysparm_query", "")

    async def test_search_without_active_filter(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        params = UserSearchParams(active_only=False)
        await service.search_users(params)
        call_params = mock_client.list_records.call_args[1]["params"]
        assert "active=true" not in call_params.get("sysparm_query", "")

    async def test_search_returns_empty_list(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        params = UserSearchParams(name="NonExistent")
        results = await service.search_users(params)
        assert results == []

    async def test_search_limit_and_offset_passed(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client.list_records.return_value = []
        params = UserSearchParams(limit=5, offset=10)
        await service.search_users(params)
        call_params = mock_client.list_records.call_args[1]["params"]
        assert call_params["sysparm_limit"] == "5"
        assert call_params["sysparm_offset"] == "10"


class TestGetCurrentUser:
    async def test_get_current_user_returns_user(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client._request.return_value = _make_user_raw()
        result = await service.get_current_user()
        assert result.user_name == "jdoe"

    async def test_get_current_user_falls_back_to_get_user(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client._request.return_value = {"user_name": "jdoe"}
        mock_client.list_records.return_value = [_make_user_raw()]
        result = await service.get_current_user()
        assert result.user_name == "jdoe"

    async def test_get_current_user_empty_response_raises(
        self, service: UserService, mock_client: MagicMock
    ) -> None:
        mock_client._request.return_value = {}
        with pytest.raises(RecordNotFoundError):
            await service.get_current_user()
