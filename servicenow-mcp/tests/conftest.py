"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

import pytest

from client.servicenow_client import ServiceNowClient
from auth.auth_provider import BasicAuthProvider


@pytest.fixture()
def mock_base_url() -> str:
    """Base URL used for all mock HTTP interactions."""
    return "https://test-instance.service-now.com"


@pytest.fixture()
def basic_auth_provider() -> BasicAuthProvider:
    """BasicAuthProvider with dummy credentials for unit tests."""
    return BasicAuthProvider(username="test_user", password="test_pass")


@pytest.fixture()
def servicenow_client(mock_base_url: str, basic_auth_provider: BasicAuthProvider) -> ServiceNowClient:
    """A ServiceNowClient wired with mock credentials (not yet open)."""
    return ServiceNowClient(
        base_url=mock_base_url,
        auth_provider=basic_auth_provider,
        timeout=10.0,
        max_retries=1,
        retry_backoff=0.1,
    )
