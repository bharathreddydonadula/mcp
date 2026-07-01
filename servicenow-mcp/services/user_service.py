"""Business service layer for ServiceNow User (sys_user) records.

This module is entirely MCP-agnostic.  It depends only on the generic
:class:`~client.ServiceNowClient` and the domain models in ``models.user``.
"""

from __future__ import annotations

import logging

from client.query_builder import QueryBuilder
from client.servicenow_client import ServiceNowClient
from exceptions.servicenow_exceptions import RecordNotFoundError
from models.user import UserResponse, UserSearchParams

logger = logging.getLogger(__name__)

_USER_TABLE = "sys_user"
_CURRENT_USER_PATH = "/api/now/ui/user/current_user"
_USER_FIELDS = [
    "sys_id",
    "user_name",
    "name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "mobile_phone",
    "department",
    "title",
    "manager",
    "active",
    "sys_created_on",
    "sys_updated_on",
]


class UserService:
    """Provides business operations on ServiceNow User records.

    Args:
        client: An open :class:`~client.ServiceNowClient` instance.
    """

    def __init__(self, client: ServiceNowClient) -> None:
        self._client = client

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _default_params() -> dict[str, str]:
        return QueryBuilder().fields(_USER_FIELDS).build()

    # ── Operations ────────────────────────────────────────────────────────────

    async def get_user(self, sys_id_or_username: str) -> UserResponse:
        """Retrieve a user by sys_id or exact username.

        Attempts a direct sys_id lookup first.  If the input is not 32 hex
        characters, falls back to a username query.

        Args:
            sys_id_or_username: Either a sys_id or the user's login username.

        Returns:
            The user record.

        Raises:
            RecordNotFoundError: If no matching user exists.
        """
        is_sys_id = (
            len(sys_id_or_username) == 32
            and all(c in "0123456789abcdef" for c in sys_id_or_username)
        )

        if is_sys_id:
            raw = await self._client.get_record(
                _USER_TABLE, sys_id_or_username, params=self._default_params()
            )
            return UserResponse.from_servicenow(raw)

        params = (
            QueryBuilder()
            .equals("user_name", sys_id_or_username)
            .fields(_USER_FIELDS)
            .limit(1)
            .build()
        )
        records = await self._client.list_records(_USER_TABLE, params=params)
        if not records:
            raise RecordNotFoundError(table=_USER_TABLE, identifier=sys_id_or_username)
        return UserResponse.from_servicenow(records[0])

    async def search_users(self, params: UserSearchParams) -> list[UserResponse]:
        """Search for users matching the given criteria.

        All criteria are optional and combined with AND logic.

        Args:
            params: A :class:`~models.UserSearchParams` with search criteria.

        Returns:
            List of matching users.
        """
        qb = QueryBuilder()

        if params.name:
            qb.like("name", params.name)
        if params.user_name:
            qb.like("user_name", params.user_name)
        if params.email:
            qb.like("email", params.email)
        if params.department:
            qb.equals("department", params.department)
        if params.active_only:
            qb.equals("active", "true")

        query_params = (
            qb.fields(_USER_FIELDS)
            .limit(params.limit)
            .offset(params.offset)
            .order_by("name")
            .build()
        )

        records = await self._client.list_records(_USER_TABLE, params=query_params)
        return [UserResponse.from_servicenow(r) for r in records]

    async def get_current_user(self) -> UserResponse:
        """Retrieve the currently authenticated user.

        Uses the ``/api/now/ui/user/current_user`` endpoint which returns
        the user associated with the credentials in the request.

        Returns:
            The current user's record.

        Raises:
            RecordNotFoundError: If the endpoint returns no user data.
        """
        logger.info("Fetching current user")
        raw = await self._client._request("GET", _CURRENT_USER_PATH)  # noqa: SLF001

        if not raw:
            raise RecordNotFoundError(table=_USER_TABLE, identifier="current_user")

        user_data = raw if "sys_id" in raw else raw.get("result", raw)
        if not isinstance(user_data, dict) or "sys_id" not in user_data:
            user_name = user_data.get("user_name", "") if isinstance(user_data, dict) else ""
            if user_name:
                return await self.get_user(user_name)
            raise RecordNotFoundError(table=_USER_TABLE, identifier="current_user")

        return UserResponse.from_servicenow(user_data)
