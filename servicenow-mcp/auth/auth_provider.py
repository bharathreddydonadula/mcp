"""Authentication provider abstractions for ServiceNow REST API access.

Two concrete implementations are provided:
- BasicAuthProvider  – HTTP Basic authentication (username + password).
- OAuthProvider      – OAuth 2.0 Resource Owner Password Credentials grant with
                       automatic token caching and refresh.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from exceptions.servicenow_exceptions import AuthenticationError

logger = logging.getLogger(__name__)

_OAUTH_TOKEN_PATH = "/oauth_token.do"
_TOKEN_EXPIRY_BUFFER_SECONDS = 60


@dataclass
class _OAuthToken:
    """Internal representation of a cached OAuth access token."""

    access_token: str
    expires_at: float  # Unix timestamp


class AuthProvider(ABC):
    """Abstract base class for ServiceNow authentication providers.

    Subclasses must implement :meth:`get_auth_headers`, which returns
    the HTTP headers required to authenticate a request.
    """

    @abstractmethod
    async def get_auth_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        """Return HTTP headers required to authenticate a request.

        Args:
            client: The shared ``httpx.AsyncClient`` instance.  OAuth
                providers use this to fetch / refresh tokens.

        Returns:
            A mapping of header name → header value.
        """


class BasicAuthProvider(AuthProvider):
    """Authenticates using HTTP Basic Auth (username + password).

    Args:
        username: ServiceNow username.
        password: ServiceNow password (plaintext; callers should source
            this from a secret store or environment variable).
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def get_auth_headers(self, client: httpx.AsyncClient) -> dict[str, str]:  # noqa: ARG002
        """Return Basic Auth header; no HTTP calls required."""
        credentials = httpx.BasicAuth(self._username, self._password)
        # Build the Authorization header value manually so we don't depend
        # on httpx internals.
        request = credentials.auth_flow(
            httpx.Request("GET", "https://placeholder")
        )
        merged: dict[str, str] = {}
        for req in request:
            for k, v in req.headers.items():
                if k.lower() == "authorization":
                    merged["Authorization"] = v
            break
        if not merged:
            # Fallback: construct header from encoded credentials
            import base64
            encoded = base64.b64encode(
                f"{self._username}:{self._password}".encode()
            ).decode()
            merged["Authorization"] = f"Basic {encoded}"
        return merged


@dataclass
class OAuthProvider(AuthProvider):
    """Authenticates using OAuth 2.0 Resource Owner Password Credentials grant.

    Fetches a token on the first request and caches it until it nears expiry,
    at which point a fresh token is obtained automatically.

    Args:
        instance_url: Base URL of the ServiceNow instance.
        client_id: OAuth application client ID.
        client_secret: OAuth application client secret.
        username: Resource owner username.
        password: Resource owner password.
    """

    instance_url: str
    client_id: str
    client_secret: str
    username: str
    password: str
    _token: _OAuthToken | None = field(default=None, init=False, repr=False)

    def _is_token_valid(self) -> bool:
        """Return True if the cached token is still usable."""
        if self._token is None:
            return False
        return time.monotonic() < (self._token.expires_at - _TOKEN_EXPIRY_BUFFER_SECONDS)

    async def _fetch_token(self, client: httpx.AsyncClient) -> _OAuthToken:
        """Request a new access token from the ServiceNow OAuth endpoint."""
        url = f"{self.instance_url}{_OAUTH_TOKEN_PATH}"
        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
        }
        logger.debug("Requesting OAuth token from %s", url)
        try:
            response = await client.post(url, data=payload)
        except httpx.RequestError as exc:
            raise AuthenticationError(
                f"Network error while fetching OAuth token: {exc}"
            ) from exc

        if response.status_code != 200:
            raise AuthenticationError(
                f"OAuth token request failed with status {response.status_code}: "
                f"{response.text}"
            )

        data = response.json()
        expires_in: int = int(data.get("expires_in", 1800))
        token = _OAuthToken(
            access_token=data["access_token"],
            expires_at=time.monotonic() + expires_in,
        )
        logger.debug("OAuth token obtained, expires in %d seconds", expires_in)
        return token

    async def get_auth_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        """Return Bearer token header, fetching or refreshing as needed."""
        if not self._is_token_valid():
            self._token = await self._fetch_token(client)
        return {"Authorization": f"Bearer {self._token.access_token}"}
