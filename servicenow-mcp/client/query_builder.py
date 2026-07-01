"""Fluent query builder that generates ServiceNow encoded query strings.

ServiceNow uses a proprietary "encoded query" syntax where conditions are
separated by ``^`` (AND) or ``^OR`` (OR).  This builder hides that syntax
behind a readable, chainable Python API and produces the full set of
``sysparm_*`` query parameters expected by the Table API.

Example::

    params = (
        QueryBuilder()
        .equals("state", "1")
        .like("short_description", "disk")
        .order_by("sys_created_on", descending=True)
        .limit(50)
        .offset(0)
        .fields(["number", "short_description", "state"])
        .build()
    )
    # {"sysparm_query": "state=1^short_descriptionLIKEdisk^ORDERBYDESCsys_created_on",
    #  "sysparm_limit": "50", "sysparm_offset": "0",
    #  "sysparm_fields": "number,short_description,state"}
"""

from __future__ import annotations

from typing import Self


class QueryBuilder:
    """Build ServiceNow Table API query parameters fluently.

    Each filter method appends a condition to the encoded query string.
    Call :meth:`build` to produce the final ``dict`` of query parameters.
    """

    def __init__(self) -> None:
        self._conditions: list[str] = []
        self._order: str | None = None
        self._limit: int | None = None
        self._offset: int | None = None
        self._fields: list[str] = []
        self._display_value: str = "false"

    # ── Filter conditions ─────────────────────────────────────────────────────

    def equals(self, field: str, value: str) -> Self:
        """Add an equality filter: ``field=value``."""
        self._conditions.append(f"{field}={value}")
        return self

    def not_equals(self, field: str, value: str) -> Self:
        """Add a not-equal filter: ``field!=value``."""
        self._conditions.append(f"{field}!={value}")
        return self

    def like(self, field: str, value: str) -> Self:
        """Add a contains filter: ``fieldLIKEvalue``."""
        self._conditions.append(f"{field}LIKE{value}")
        return self

    def not_like(self, field: str, value: str) -> Self:
        """Add a not-contains filter: ``fieldNOTLIKEvalue``."""
        self._conditions.append(f"{field}NOTLIKE{value}")
        return self

    def starts_with(self, field: str, value: str) -> Self:
        """Add a starts-with filter: ``fieldSTARTSWITHvalue``."""
        self._conditions.append(f"{field}STARTSWITH{value}")
        return self

    def ends_with(self, field: str, value: str) -> Self:
        """Add an ends-with filter: ``fieldENDSWITHvalue``."""
        self._conditions.append(f"{field}ENDSWITH{value}")
        return self

    def greater_than(self, field: str, value: str) -> Self:
        """Add a greater-than filter: ``field>value``."""
        self._conditions.append(f"{field}>{value}")
        return self

    def less_than(self, field: str, value: str) -> Self:
        """Add a less-than filter: ``field<value``."""
        self._conditions.append(f"{field}<{value}")
        return self

    def greater_than_or_equal(self, field: str, value: str) -> Self:
        """Add a greater-than-or-equal filter: ``field>=value``."""
        self._conditions.append(f"{field}>={value}")
        return self

    def less_than_or_equal(self, field: str, value: str) -> Self:
        """Add a less-than-or-equal filter: ``field<=value``."""
        self._conditions.append(f"{field}<={value}")
        return self

    def is_empty(self, field: str) -> Self:
        """Add an is-empty filter: ``fieldISEMPTY``."""
        self._conditions.append(f"{field}ISEMPTY")
        return self

    def is_not_empty(self, field: str) -> Self:
        """Add an is-not-empty filter: ``fieldISNOTEMPTY``."""
        self._conditions.append(f"{field}ISNOTEMPTY")
        return self

    # ── Sorting ───────────────────────────────────────────────────────────────

    def order_by(self, field: str, *, descending: bool = False) -> Self:
        """Set the sort order.

        Args:
            field: Field name to sort by.
            descending: If ``True``, sort descending (ORDERBYDESC); otherwise ascending.
        """
        prefix = "ORDERBYDESC" if descending else "ORDERBY"
        self._order = f"{prefix}{field}"
        return self

    # ── Pagination ────────────────────────────────────────────────────────────

    def limit(self, value: int) -> Self:
        """Set the maximum number of records to return (``sysparm_limit``)."""
        self._limit = value
        return self

    def offset(self, value: int) -> Self:
        """Set the zero-based record offset (``sysparm_offset``)."""
        self._offset = value
        return self

    # ── Field selection ───────────────────────────────────────────────────────

    def fields(self, field_names: list[str]) -> Self:
        """Restrict which fields are returned (``sysparm_fields``)."""
        self._fields = list(field_names)
        return self

    # ── Display values ────────────────────────────────────────────────────────

    def display_value(self, mode: str = "true") -> Self:
        """Control ``sysparm_display_value``.

        Args:
            mode: ``"true"`` (display values only), ``"false"`` (raw values only),
                or ``"all"`` (both).
        """
        self._display_value = mode
        return self

    # ── Build ─────────────────────────────────────────────────────────────────

    def build(self) -> dict[str, str]:
        """Produce the final ``sysparm_*`` query parameter dictionary.

        Returns:
            A dictionary ready to be passed as ``params=`` to an httpx request.
        """
        parts = list(self._conditions)
        if self._order:
            parts.append(self._order)

        params: dict[str, str] = {}
        if parts:
            params["sysparm_query"] = "^".join(parts)
        if self._limit is not None:
            params["sysparm_limit"] = str(self._limit)
        if self._offset is not None:
            params["sysparm_offset"] = str(self._offset)
        if self._fields:
            params["sysparm_fields"] = ",".join(self._fields)
        if self._display_value != "false":
            params["sysparm_display_value"] = self._display_value

        return params

    def encoded_query(self) -> str:
        """Return just the encoded query string (value of ``sysparm_query``).

        Returns an empty string when no conditions have been added.
        """
        return self.build().get("sysparm_query", "")
