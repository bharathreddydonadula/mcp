"""Unit tests for ServiceNowClient using mocked HTTP responses."""

from __future__ import annotations

import pytest
import httpx
from pytest_httpx import HTTPXMock

from client.servicenow_client import ServiceNowClient
from auth.auth_provider import BasicAuthProvider
from exceptions.servicenow_exceptions import (
    AuthenticationError,
    AuthorizationError,
    RecordNotFoundError,
    ServiceNowValidationError,
    RateLimitError,
)

BASE_URL = "https://test-instance.service-now.com"
TABLE_API = f"{BASE_URL}/api/now/table"


@pytest.fixture()
def client() -> ServiceNowClient:
    return ServiceNowClient(
        base_url=BASE_URL,
        auth_provider=BasicAuthProvider("user", "pass"),
        timeout=5.0,
        max_retries=1,
        retry_backoff=0.01,
    )


@pytest.fixture()
async def open_client(client: ServiceNowClient) -> ServiceNowClient:
    await client._open()
    return client


class TestCreateRecord:
    async def test_create_record_returns_result(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{TABLE_API}/incident",
            json={"result": {"sys_id": "abc123", "number": "INC0001"}},
            status_code=201,
        )
        result = await open_client.create_record("incident", {"short_description": "Test"})
        assert result["sys_id"] == "abc123"
        assert result["number"] == "INC0001"

    async def test_create_record_401_raises_auth_error(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{TABLE_API}/incident",
            json={"error": {"message": "User Not Authenticated", "detail": ""}},
            status_code=401,
        )
        with pytest.raises(AuthenticationError):
            await open_client.create_record("incident", {"short_description": "Test"})

    async def test_create_record_400_raises_validation_error(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{TABLE_API}/incident",
            json={"error": {"message": "Invalid field", "detail": "short_description required"}},
            status_code=400,
        )
        with pytest.raises(ServiceNowValidationError):
            await open_client.create_record("incident", {})


class TestGetRecord:
    async def test_get_record_success(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{TABLE_API}/incident/abc123",
            json={"result": {"sys_id": "abc123", "number": "INC0001"}},
            status_code=200,
        )
        result = await open_client.get_record("incident", "abc123")
        assert result["sys_id"] == "abc123"

    async def test_get_record_404_raises_not_found(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{TABLE_API}/incident/notexist",
            json={"error": {"message": "No Record found", "detail": ""}},
            status_code=404,
        )
        with pytest.raises(RecordNotFoundError) as exc_info:
            await open_client.get_record("incident", "notexist")
        assert exc_info.value.table == "incident"
        assert exc_info.value.identifier == "notexist"

    async def test_get_record_403_raises_authorization_error(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{TABLE_API}/incident/abc123",
            json={"error": {"message": "Forbidden", "detail": ""}},
            status_code=403,
        )
        with pytest.raises(AuthorizationError):
            await open_client.get_record("incident", "abc123")


class TestListRecords:
    async def test_list_records_returns_list(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{TABLE_API}/incident",
            json={"result": [{"sys_id": "a1"}, {"sys_id": "a2"}]},
            status_code=200,
        )
        result = await open_client.list_records("incident")
        assert len(result) == 2
        assert result[0]["sys_id"] == "a1"

    async def test_list_records_empty_returns_empty_list(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{TABLE_API}/incident",
            json={"result": []},
            status_code=200,
        )
        result = await open_client.list_records("incident")
        assert result == []


class TestUpdateRecord:
    async def test_update_record_success(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="PATCH",
            url=f"{TABLE_API}/incident/abc123",
            json={"result": {"sys_id": "abc123", "state": "2"}},
            status_code=200,
        )
        result = await open_client.update_record("incident", "abc123", {"state": "2"})
        assert result["state"] == "2"

    async def test_update_record_404_raises_not_found(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="PATCH",
            url=f"{TABLE_API}/incident/notexist",
            json={"error": {"message": "No Record found", "detail": ""}},
            status_code=404,
        )
        with pytest.raises(RecordNotFoundError):
            await open_client.update_record("incident", "notexist", {"state": "2"})


class TestDeleteRecord:
    async def test_delete_record_success(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{TABLE_API}/incident/abc123",
            status_code=204,
        )
        await open_client.delete_record("incident", "abc123")

    async def test_delete_record_404_raises_not_found(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{TABLE_API}/incident/notexist",
            json={"error": {"message": "No Record found", "detail": ""}},
            status_code=404,
        )
        with pytest.raises(RecordNotFoundError):
            await open_client.delete_record("incident", "notexist")


class TestRateLimiting:
    async def test_429_raises_rate_limit_error(
        self, open_client: ServiceNowClient, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{TABLE_API}/incident/abc123",
            json={"error": {"message": "Rate limit exceeded", "detail": ""}},
            status_code=429,
            headers={"Retry-After": "30"},
        )
        with pytest.raises(RateLimitError) as exc_info:
            await open_client.get_record("incident", "abc123")
        assert exc_info.value.retry_after == 30
