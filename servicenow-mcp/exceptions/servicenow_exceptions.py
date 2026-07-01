"""Structured exception hierarchy for the ServiceNow MCP server."""

from __future__ import annotations


class ServiceNowError(Exception):
    """Base exception for all ServiceNow-related errors.

    All other exceptions in this module inherit from this class,
    enabling callers to catch the full hierarchy with a single except clause.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r}, status_code={self.status_code})"


class AuthenticationError(ServiceNowError):
    """Raised when ServiceNow rejects credentials (HTTP 401).

    Indicates invalid username/password or expired OAuth token.
    """

    def __init__(self, message: str = "Authentication failed. Check credentials.") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(ServiceNowError):
    """Raised when the authenticated user lacks permission (HTTP 403).

    The request was understood but the user does not have the required role.
    """

    def __init__(self, message: str = "Authorization failed. Insufficient permissions.") -> None:
        super().__init__(message, status_code=403)


class RecordNotFoundError(ServiceNowError):
    """Raised when a requested record does not exist in ServiceNow (HTTP 404).

    Attributes:
        table: The ServiceNow table that was queried.
        identifier: The sys_id or number that was not found.
    """

    def __init__(
        self,
        table: str,
        identifier: str,
        message: str | None = None,
    ) -> None:
        self.table = table
        self.identifier = identifier
        msg = message or f"Record '{identifier}' not found in table '{table}'."
        super().__init__(msg, status_code=404)


class ServiceNowValidationError(ServiceNowError):
    """Raised when ServiceNow rejects the request payload (HTTP 400).

    Attributes:
        field_errors: Optional mapping of field names to validation messages.
    """

    def __init__(
        self,
        message: str,
        *,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message, status_code=400)
        self.field_errors = field_errors or {}


class RateLimitError(ServiceNowError):
    """Raised when ServiceNow enforces rate limiting (HTTP 429).

    Attributes:
        retry_after: Optional seconds to wait before retrying, from Retry-After header.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded. Slow down requests.",
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ServiceNowTimeoutError(ServiceNowError):
    """Raised when an HTTP request to ServiceNow times out."""

    def __init__(self, message: str = "Request to ServiceNow timed out.") -> None:
        super().__init__(message)


class ServiceNowHTTPError(ServiceNowError):
    """Raised for unexpected HTTP errors not covered by more specific exceptions.

    Attributes:
        response_body: Raw response body text for debugging.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: str = "",
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.response_body = response_body
