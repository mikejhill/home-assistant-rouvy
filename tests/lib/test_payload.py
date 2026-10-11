"""Tests for Payload navigation and Fields accessors."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

import pytest

from rouvy_api import Fields, Payload, TaggedValue, TurboValue


class TestFields:
    """Typed, forgiving accessors."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("x", "x"), ("", None), (3, None), (None, None)],
    )
    def test_text(self, value: TurboValue, expected: str | None) -> None:
        """text() returns only non-empty strings."""
        assert Fields({"k": value}).text("k") == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (3, 3.0),
            (2.5, 2.5),
            ("4.5", 4.5),
            ("abc", None),
            ("INF", None),
            ("-inf", None),
            ("NaN", None),
            (True, None),
            (math.nan, None),
            (math.inf, None),
            (None, None),
            ([1], None),
        ],
    )
    def test_number(self, value: TurboValue, expected: float | None) -> None:
        """number() accepts finite numbers and numeric strings, not booleans."""
        assert Fields({"k": value}).number("k") == expected

    def test_integer_rejects_non_finite_strings(self) -> None:
        """integer() returns None for "INF" instead of raising OverflowError."""
        assert Fields({"k": "INF"}).integer("k") is None

    def test_integer_rounds(self) -> None:
        """integer() rounds integral-looking values."""
        assert Fields({"k": 164.6}).integer("k") == 165
        assert Fields({}).integer("k") is None

    def test_flag(self) -> None:
        """flag() is True only for a literal True."""
        assert Fields({"a": True, "b": 1, "c": "true"}).flag("a") is True
        assert Fields({"a": True, "b": 1, "c": "true"}).flag("b") is False
        assert Fields({"a": True, "b": 1, "c": "true"}).flag("c") is False

    def test_has(self) -> None:
        """has() ignores keys holding None."""
        fields = Fields({"a": None, "b": 0})

        assert not fields.has("a")
        assert fields.has("b")
        assert not fields.has("c")

    def test_nested_accessors(self) -> None:
        """mapping, records, numbers, and strings filter by element type."""
        fields = Fields(
            {
                "m": {"x": 1},
                "r": [{"a": 1}, 2, {"b": 2}],
                "n": [1, "2", 3.5, True],
                "s": ["a", 1, "b"],
                "bad": "nope",
            }
        )

        assert fields.mapping("m") is not None
        assert fields.mapping("bad") is None
        assert [r.raw for r in fields.records("r")] == [{"a": 1}, {"b": 2}]
        assert fields.records("bad") == []
        assert fields.numbers("n") == [1.0, 3.5]
        assert fields.numbers("bad") == []
        assert fields.strings("s") == ["a", "b"]
        assert fields.strings("bad") == []

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (datetime(2026, 1, 2, 3, 4, tzinfo=UTC), datetime(2026, 1, 2, 3, 4, tzinfo=UTC)),
            (datetime(2026, 1, 2, 3, 4), datetime(2026, 1, 2, 3, 4, tzinfo=UTC)),  # noqa: DTZ001 - naive input under test
            ("2026-01-02T03:04:00.000Z", datetime(2026, 1, 2, 3, 4, tzinfo=UTC)),
            ("2026-01-02T03:04:00", datetime(2026, 1, 2, 3, 4, tzinfo=UTC)),
            ("not a date", None),
            ("", None),
            (5, None),
        ],
    )
    def test_timestamp(self, value: TurboValue, expected: datetime | None) -> None:
        """timestamp() accepts decoded dates and ISO strings, assuming UTC when naive."""
        assert Fields({"k": value}).timestamp("k") == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-10-05", date(2026, 10, 5)),
            ("2026-13-05", None),
            ("2026-10-05T23:00:00Z", date(2026, 10, 5)),
            (datetime(2026, 10, 5, tzinfo=UTC), date(2026, 10, 5)),
            (None, None),
        ],
    )
    def test_day(self, value: TurboValue, expected: date | None) -> None:
        """day() accepts plain dates, timestamps, and decoded dates."""
        assert Fields({"k": value}).day("k") == expected

    def test_wrap(self) -> None:
        """wrap() only wraps dicts."""
        assert Fields.wrap({"a": 1}) is not None
        assert Fields.wrap([1]) is None


class TestPayload:
    """Breadth-first lookup and redirect detection."""

    def test_find_prefers_shallowest(self) -> None:
        """find() returns the shallowest match."""
        payload = Payload({"deep": {"deeper": {"email": "deep"}}, "email": "top"})

        assert payload.find("email") == "top"
        assert payload.find("missing") is None

    def test_find_fields_and_records(self) -> None:
        """Typed finders skip values of the wrong type."""
        payload = Payload(
            {"a": {"items": "not a list"}, "b": {"items": [{"x": 1}, 2]}, "c": {"obj": {"y": 2}}}
        )

        records = payload.find_records("items")
        fields = payload.find_fields("obj")
        assert records is not None
        assert [r.raw for r in records] == [{"x": 1}]
        assert fields is not None
        assert fields.raw == {"y": 2}
        assert payload.find_records("missing") is None
        assert payload.find_fields("missing") is None

    def test_objects_with(self) -> None:
        """objects_with() yields every object holding the key."""
        payload = Payload([{"k": 1}, {"nested": {"k": 2}}, {"other": 3}])

        assert [f.raw["k"] for f in payload.objects_with("k")] == [1, 2]

    def test_walk_handles_cycles(self) -> None:
        """Cyclic payloads are walked once."""
        node: dict[str, TurboValue] = {"name": "x"}
        node["self"] = node

        assert Payload(node).find("missing") is None

    def test_tagged_redirect(self) -> None:
        """SingleFetchRedirect payloads expose their target."""
        payload = Payload(
            TaggedValue("SingleFetchRedirect", ({"redirect": "/feed", "status": 302},))
        )

        assert payload.redirect_location == "/feed"

    def test_plain_redirect(self) -> None:
        """Action redirects are plain objects with redirect and status."""
        assert (
            Payload({"redirect": "/check-inbox", "status": 302}).redirect_location == "/check-inbox"
        )

    @pytest.mark.parametrize(
        "root",
        [{"data": 1}, {"redirect": "/x"}, TaggedValue("Other", ()), "text", None],
    )
    def test_not_a_redirect(self, root: TurboValue) -> None:
        """Other shapes are not redirects."""
        assert Payload(root).redirect_location is None

    def test_action_data(self) -> None:
        """action_data returns the root data object."""
        data = Payload({"data": {"status": "error"}}).action_data

        assert data is not None
        assert data.text("status") == "error"
        assert Payload([1]).action_data is None

    def test_parse(self) -> None:
        """parse() decodes turbo-stream text."""
        assert Payload.parse('[{"_1":2},"a","b"]').root == {"a": "b"}
