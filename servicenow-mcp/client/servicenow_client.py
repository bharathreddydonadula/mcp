"""Generic ServiceNow REST client.

This module provides a table-agnostic HTTP client that wraps the ServiceNow
Table API.  It handles authentication, retries, timeouts, and error translation
so that higher-level service classes can focus entirely on business logic.

Usage::

    async with ServiceNowClient.from_settings() as client:
        record = await client.get_record("incident", sys_id="abc123")
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from auth.auth_provider import AuthProvider, BasicAuthProvider, OAuthProvider
from config import AuthMode, Settings, get_settings
from exceptions.servicenow_exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    RecordNotFoundError,
    ServiceNowHTTPError,
    ServiceNowTimeoutError,
    ServiceNowValidationError,
)

logger = logging.getLogger(__name__)

_TABLE_API_BASE = "/api/now/table"
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


class ServiceNowClient:
    """Async HTTP client for the ServiceNow Table API.

    This class is table-agnostic: every method receives the target table name
    as its first argument.  No business logic lives here — only generic CRUD
    operations.

    Prefer creating instances via :meth:`from_settings` or as an async context
    manager.

    Args:
        base_url: Base URL of the ServiceNow instance.
        auth_provider: An :class:`~auth.AuthProvider` implementation.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum retry attempts for transient failures.
        retry_backoff: Initial backoff time between retries (exponential).
    """

    def __init__(
        self,
        base_url: str,
        auth_provider: AuthProvider,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_provider = auth_provider
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._http_client: httpx.AsyncClient | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def __aenter__(self) -> ServiceNowClient:
        await self._open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._close()

    async def _open(self) -> None:
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        )

    async def _close(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            raise RuntimeError(
                "ServiceNowClient is not open. Use 'async with' or call _open() first."
            )
        return self._http_client

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ServiceNowClient:
        """Construct a client from application settings.

        Args:
            settings: Optional :class:`~config.Settings` instance.  Defaults
                to the cached singleton from :func:`~config.get_settings`.

        Returns:
            A configured :class:`ServiceNowClient` (not yet open).
        """
        cfg = settings or get_settings()
        auth_provider: AuthProvider
        if cfg.servicenow_auth_mode == AuthMode.OAUTH:
            auth_provider = OAuthProvider(
                instance_url=cfg.instance_url,
                client_id=cfg.servicenow_client_id,
                client_secret=cfg.servicenow_client_secret.get_secret_value(),
                username=cfg.servicenow_username,
                password=cfg.servicenow_password.get_secret_value(),
            )
        else:
            auth_provider = BasicAuthProvider(
                username=cfg.servicenow_username,
                password=cfg.servicenow_password.get_secret_value(),
            )

        return cls(
            base_url=cfg.instance_url,
            auth_provider=auth_provider,
            timeout=cfg.servicenow_timeout_seconds,
            max_retries=cfg.servicenow_max_retries,
            retry_backoff=cfg.servicenow_retry_backoff,
        )

    # ── Core HTTP ─────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an authenticated HTTP request with retry logic.

        Args:
            method: HTTP verb (GET, POST, PATCH, DELETE).
            path: URL path relative to the instance base URL.
            params: Optional query parameters.
            json: Optional JSON request body.

        Returns:
            Parsed JSON response body as a dictionary.

        Raises:
            AuthenticationError: On HTTP 401.
            AuthorizationError: On HTTP 403.
            RecordNotFoundError: On HTTP 404 (re-raised by callers with context).
            ServiceNowValidationError: On HTTP 400.
            RateLimitError: On HTTP 429.
            ServiceNowHTTPError: For other non-2xx responses.
            ServiceNowTimeoutError: On request timeout.
        """
        url = f"{self._base_url}{path}"
        auth_headers = await self._auth_provider.get_auth_headers(self._client)
        headers = {**_DEFAULT_HEADERS, **auth_headers}

        logger.debug("%s %s params=%s", method, url, params)

        @retry(
            retry=retry_if_exception_type((ServiceNowHTTPError, ServiceNowTimeoutError)),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._retry_backoff, min=1, max=30),
            reraise=True,
        )
        async def _execute() -> dict[str, Any]:
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )
            except httpx.TimeoutException as exc:
                raise ServiceNowTimeoutError() from exc
            except httpx.RequestError as exc:
                raise ServiceNowHTTPError(
                    f"Network error: {exc}",
                    status_code=0,
                    response_body="",
                ) from exc

            return self._handle_response(response)

        return await _execute()

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse and validate an HTTP response.

        Args:
            response: The raw httpx response object.

        Returns:
            The ``result`` key from the ServiceNow JSON envelope, or the full
            body if the key is absent (e.g. DELETE responses).

        Raises:
            AuthenticationError: On 401.
            AuthorizationError: On 403.
            ServiceNowValidationError: On 400.
            RateLimitError: On 429.
            ServiceNowHTTPError: For other non-2xx status codes.
        """
        logger.debug("Response: %d %s", response.status_code, response.url)

        if response.status_code == 204:
            return {}

        try:
            body: dict[str, Any] = response.json()
        except Exception:
            body = {"raw": response.text}

        if response.is_success:
            return body.get("result", body)  # type: ignore[return-value]

        error_msg = self._extract_error_message(body, response.status_code)

        if response.status_code == 401:
            raise AuthenticationError(error_msg)
        if response.status_code == 403:
            raise AuthorizationError(error_msg)
        if response.status_code == 400:
            raise ServiceNowValidationError(error_msg)
        if response.status_code == 404:
            # Raised by callers with richer context; use a generic sentinel here.
            raise RecordNotFoundError(table="unknown", identifier="unknown", message=error_msg)
        if response.status_code == 429:
            retry_after_raw = response.headers.get("Retry-After")
            retry_after = int(retry_after_raw) if retry_after_raw else None
            raise RateLimitError(error_msg, retry_after=retry_after)

        # Only retry on 5xx
        if response.status_code >= 500:
            raise ServiceNowHTTPError(
                error_msg,
                status_code=response.status_code,
                response_body=response.text,
            )

        raise ServiceNowHTTPError(
            error_msg,
            status_code=response.status_code,
            response_body=response.text,
        )

    @staticmethod
    def _extract_error_message(body: dict[str, Any], status_code: int) -> str:
        """Extract a human-readable error message from a ServiceNow error response."""
        if "error" in body:
            error = body["error"]
            if isinstance(error, dict):
                detail = error.get("detail", "")
                message = error.get("message", "")
                return f"{message}: {detail}".strip(": ") or f"HTTP {status_code}"
        return body.get("message", f"HTTP {status_code}")

    # ── Generic CRUD ──────────────────────────────────────────────────────────

    async def create_record(
        self,
        table: str,
        data: dict[str, Any],
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a new record in the specified table.

        Args:
            table: ServiceNow table name (e.g. ``"incident"``).
            data: Field values for the new record.
            params: Optional extra query parameters.

        Returns:
            The created record as returned by ServiceNow.
        """
        logger.info("Creating record in table '%s'", table)
        path = f"{_TABLE_API_BASE}/{table}"
        return await self._request("POST", path, params=params, json=data)

    async def get_record(
        self,
        table: str,
        sys_id: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve a single record by sys_id.

        Args:
            table: ServiceNow table name.
            sys_id: The ``sys_id`` of the record to retrieve.
            params: Optional query parameters (e.g. ``sysparm_fields``).

        Returns:
            The record dictionary.

        Raises:
            RecordNotFoundError: If the record does not exist.
        """
        logger.info("Fetching record %s from table '%s'", sys_id, table)
        path = f"{_TABLE_API_BASE}/{table}/{sys_id}"
        try:
            return await self._request("GET", path, params=params)
        except RecordNotFoundError:
            raise RecordNotFoundError(table=table, identifier=sys_id) from None

    async def list_records(
        self,
        table: str,
        *,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """List records from a table with optional filtering and pagination.

        Args:
            table: ServiceNow table name.
            params: Query parameters including ``sysparm_query``, ``sysparm_limit``,
                ``sysparm_offset``, and ``sysparm_fields``.

        Returns:
            A list of record dictionaries.
        """
        logger.info("Listing records from table '%s' params=%s", table, params)
        path = f"{_TABLE_API_BASE}/{table}"
        result = await self._request("GET", path, params=params)
        if isinstance(result, list):
            return result  # type: ignore[return-value]
        return []

    async def update_record(
        self,
        table: str,
        sys_id: str,
        data: dict[str, Any],
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing record by sys_id (PATCH).

        Args:
            table: ServiceNow table name.
            sys_id: The ``sys_id`` of the record to update.
            data: Fields to update (partial update supported).
            params: Optional extra query parameters.

        Returns:
            The updated record.

        Raises:
            RecordNotFoundError: If the record does not exist.
        """
        logger.info("Updating record %s in table '%s'", sys_id, table)
        path = f"{_TABLE_API_BASE}/{table}/{sys_id}"
        try:
            return await self._request("PATCH", path, params=params, json=data)
        except RecordNotFoundError:
            raise RecordNotFoundError(table=table, identifier=sys_id) from None

    async def delete_record(
        self,
        table: str,
        sys_id: str,
    ) -> None:
        """Delete a record by sys_id.

        Args:
            table: ServiceNow table name.
            sys_id: The ``sys_id`` of the record to delete.

        Raises:
            RecordNotFoundError: If the record does not exist.
        """
        logger.info("Deleting record %s from table '%s'", sys_id, table)
        path = f"{_TABLE_API_BASE}/{table}/{sys_id}"
        try:
            await self._request("DELETE", path)
        except RecordNotFoundError:
            raise RecordNotFoundError(table=table, identifier=sys_id) from None
