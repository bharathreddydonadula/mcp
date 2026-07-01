"""Unit tests for the QueryBuilder class."""

from __future__ import annotations

import pytest

from client.query_builder import QueryBuilder


class TestQueryBuilderFilters:
    """Tests for individual filter condition methods."""

    def test_equals(self) -> None:
        params = QueryBuilder().equals("state", "1").build()
        assert params["sysparm_query"] == "state=1"

    def test_not_equals(self) -> None:
        params = QueryBuilder().not_equals("state", "7").build()
        assert params["sysparm_query"] == "state!=7"

    def test_like(self) -> None:
        params = QueryBuilder().like("short_description", "disk").build()
        assert params["sysparm_query"] == "short_descriptionLIKEdisk"

    def test_not_like(self) -> None:
        params = QueryBuilder().not_like("short_description", "test").build()
        assert params["sysparm_query"] == "short_descriptionNOTLIKEtest"

    def test_starts_with(self) -> None:
        params = QueryBuilder().starts_with("number", "INC").build()
        assert params["sysparm_query"] == "numberSTARTSWITHINC"

    def test_ends_with(self) -> None:
        params = QueryBuilder().ends_with("number", "001").build()
        assert params["sysparm_query"] == "numberENDSWITH001"

    def test_greater_than(self) -> None:
        params = QueryBuilder().greater_than("priority", "2").build()
        assert params["sysparm_query"] == "priority>2"

    def test_less_than(self) -> None:
        params = QueryBuilder().less_than("priority", "4").build()
        assert params["sysparm_query"] == "priority<4"

    def test_greater_than_or_equal(self) -> None:
        params = QueryBuilder().greater_than_or_equal("priority", "2").build()
        assert params["sysparm_query"] == "priority>=2"

    def test_less_than_or_equal(self) -> None:
        params = QueryBuilder().less_than_or_equal("priority", "4").build()
        assert params["sysparm_query"] == "priority<=4"

    def test_is_empty(self) -> None:
        params = QueryBuilder().is_empty("resolved_at").build()
        assert params["sysparm_query"] == "resolved_atISEMPTY"

    def test_is_not_empty(self) -> None:
        params = QueryBuilder().is_not_empty("resolved_at").build()
        assert params["sysparm_query"] == "resolved_atISNOTEMPTY"


class TestQueryBuilderChaining:
    """Tests for chaining multiple conditions."""

    def test_multiple_conditions_joined_by_caret(self) -> None:
        params = (
            QueryBuilder()
            .equals("state", "1")
            .equals("priority", "2")
            .build()
        )
        assert params["sysparm_query"] == "state=1^priority=2"

    def test_three_conditions(self) -> None:
        params = (
            QueryBuilder()
            .equals("state", "1")
            .like("short_description", "disk")
            .not_equals("category", "hardware")
            .build()
        )
        assert params["sysparm_query"] == (
            "state=1^short_descriptionLIKEdisk^category!=hardware"
        )


class TestQueryBuilderSorting:
    """Tests for ordering."""

    def test_order_by_ascending(self) -> None:
        params = QueryBuilder().order_by("sys_created_on").build()
        assert "ORDERBYsys_created_on" in params["sysparm_query"]

    def test_order_by_descending(self) -> None:
        params = QueryBuilder().order_by("sys_created_on", descending=True).build()
        assert "ORDERBYDESCsys_created_on" in params["sysparm_query"]

    def test_order_appended_after_conditions(self) -> None:
        params = (
            QueryBuilder()
            .equals("state", "1")
            .order_by("sys_created_on", descending=True)
            .build()
        )
        assert params["sysparm_query"] == "state=1^ORDERBYDESCsys_created_on"


class TestQueryBuilderPagination:
    """Tests for limit and offset."""

    def test_limit(self) -> None:
        params = QueryBuilder().limit(50).build()
        assert params["sysparm_limit"] == "50"

    def test_offset(self) -> None:
        params = QueryBuilder().offset(100).build()
        assert params["sysparm_offset"] == "100"

    def test_limit_and_offset(self) -> None:
        params = QueryBuilder().limit(10).offset(20).build()
        assert params["sysparm_limit"] == "10"
        assert params["sysparm_offset"] == "20"


class TestQueryBuilderFields:
    """Tests for field selection."""

    def test_fields_comma_separated(self) -> None:
        params = QueryBuilder().fields(["sys_id", "number", "state"]).build()
        assert params["sysparm_fields"] == "sys_id,number,state"

    def test_single_field(self) -> None:
        params = QueryBuilder().fields(["sys_id"]).build()
        assert params["sysparm_fields"] == "sys_id"


class TestQueryBuilderDisplayValue:
    """Tests for display_value."""

    def test_display_value_default_not_included(self) -> None:
        params = QueryBuilder().build()
        assert "sysparm_display_value" not in params

    def test_display_value_true(self) -> None:
        params = QueryBuilder().display_value("true").build()
        assert params["sysparm_display_value"] == "true"

    def test_display_value_all(self) -> None:
        params = QueryBuilder().display_value("all").build()
        assert params["sysparm_display_value"] == "all"


class TestQueryBuilderEmpty:
    """Tests for empty builder behaviour."""

    def test_empty_build_returns_empty_dict(self) -> None:
        params = QueryBuilder().build()
        assert params == {}

    def test_encoded_query_empty_string(self) -> None:
        assert QueryBuilder().encoded_query() == ""

    def test_encoded_query_with_conditions(self) -> None:
        q = QueryBuilder().equals("state", "1").encoded_query()
        assert q == "state=1"


class TestQueryBuilderFullExample:
    """Integration-style test combining all features."""

    def test_full_query(self) -> None:
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
        assert params["sysparm_query"] == (
            "state=1^short_descriptionLIKEdisk^ORDERBYDESCsys_created_on"
        )
        assert params["sysparm_limit"] == "50"
        assert params["sysparm_offset"] == "0"
        assert params["sysparm_fields"] == "number,short_description,state"
