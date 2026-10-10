"""Tests for the turbo-stream decoder."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rouvy_api import RouvyResponseError, TaggedValue, TurboStreamDecoder
from tests.support.rouvy_payloads import FIXTURES_DIR


class TestScalarsAndSentinels:
    """Primitive values and negative sentinel indices."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ('["hello"]', "hello"),
            ("[42]", 42),
            ("[true]", True),
            ("-5", None),
            ("-7", None),
            ("-1", None),
            ("-6", math.inf),
            ("-3", -math.inf),
        ],
    )
    def test_values(self, text: str, expected: object) -> None:
        """Literal roots and sentinel constants decode to Python values."""
        assert TurboStreamDecoder().decode(text) == expected

    def test_nan_and_negative_zero(self) -> None:
        """NaN and -0.0 sentinels keep their special float identity."""
        nan = TurboStreamDecoder().decode("-2")
        neg_zero = TurboStreamDecoder().decode("-4")

        assert isinstance(nan, float)
        assert math.isnan(nan)
        assert neg_zero == 0.0
        assert isinstance(neg_zero, float)
        assert math.copysign(1, neg_zero) == -1

    def test_unknown_constant(self) -> None:
        """An unknown negative index is rejected."""
        with pytest.raises(RouvyResponseError, match="constant"):
            TurboStreamDecoder().decode("[[ -99 ]]")


class TestContainers:
    """Objects, arrays, and references."""

    def test_object_with_indexed_keys(self) -> None:
        """Object keys and values are both indices."""
        decoded = TurboStreamDecoder().decode('[{"_1":2,"_3":-5},"name","Ada","team"]')

        assert decoded == {"name": "Ada", "team": None}

    def test_array_of_indices(self) -> None:
        """Arrays hold indices, and holes decode to None."""
        decoded = TurboStreamDecoder().decode('[[1,2,-1],"a",7]')

        assert decoded == ["a", 7, None]

    def test_shared_reference_is_same_object(self) -> None:
        """Two references to one index decode to the same object."""
        decoded = TurboStreamDecoder().decode('[{"_1":3,"_2":3},"a","b",{"_4":5},"x",1]')

        assert isinstance(decoded, dict)
        assert decoded["a"] is decoded["b"]

    def test_cycle(self) -> None:
        """Self-referencing objects decode without infinite recursion."""
        decoded = TurboStreamDecoder().decode('[{"_1":0},"self"]')

        assert isinstance(decoded, dict)
        assert decoded["self"] is decoded

    def test_non_string_key_is_stringified(self) -> None:
        """A key index that points at a number becomes its string form."""
        decoded = TurboStreamDecoder().decode('[{"_1":2},5,"five"]')

        assert decoded == {"5": "five"}


class TestTypedValues:
    """Tagged arrays: dates, promises, sets, maps, and plugin types."""

    def test_date_is_aware_utc(self) -> None:
        """Dates decode to timezone-aware UTC datetimes."""
        decoded = TurboStreamDecoder().decode('[["D",1760054400000]]')

        assert decoded == datetime(2025, 10, 10, tzinfo=UTC)

    @pytest.mark.parametrize("text", ['[["D","soon"]]', '[["D",1e300]]', '[["D"]]'])
    def test_invalid_date_is_none(self, text: str) -> None:
        """Unusable timestamps decode to None instead of failing."""
        assert TurboStreamDecoder().decode(text) is None

    def test_set_and_map(self) -> None:
        """Sets become lists and maps become dicts."""
        decoded = TurboStreamDecoder().decode(
            '[{"_1":2,"_3":4},"s",["S",5,6],"m",["M",5,6],"k","v"]'
        )

        assert decoded == {"s": ["k", "v"], "m": {"k": "v"}}

    def test_previous_reference(self) -> None:
        """A Z tag points at an earlier value."""
        decoded = TurboStreamDecoder().decode('[[1,2],"x",["Z",1]]')

        assert decoded == ["x", "x"]

    def test_literal_tags(self) -> None:
        """URL-like literal tags keep their raw arguments."""
        decoded = TurboStreamDecoder().decode('[["U","https://rouvy.com"]]')

        assert decoded == TaggedValue("U", ("https://rouvy.com",))

    def test_plugin_tag(self) -> None:
        """Unknown tags such as SingleFetchRedirect hydrate their arguments."""
        decoded = TurboStreamDecoder().decode(
            '[["SingleFetchRedirect",1],{"_2":3,"_4":5},"redirect","/x","status",302]'
        )

        assert decoded == TaggedValue("SingleFetchRedirect", ({"redirect": "/x", "status": 302},))


class TestPromises:
    """Deferred values resolved on later lines."""

    def test_array_promise_line(self) -> None:
        """Array promise lines append to the global index space."""
        text = '[{"_1":2},"later",["P",7]]\nP7:[{"_4":5},"total",3]\n'

        assert TurboStreamDecoder().decode(text) == {"later": {"total": 3}}

    def test_numeric_promise_line(self) -> None:
        """A numeric promise line references an existing index."""
        text = '[{"_1":2},"later",["P",1]]\nP1:-5\n'

        assert TurboStreamDecoder().decode(text) == {"later": None}

    def test_rejected_and_unresolved(self) -> None:
        """Rejected and never-resolved promises decode to None."""
        text = '[{"_1":2,"_3":4},"bad",["P",1],"missing",["P",9]]\nE1:["boom"]\n'

        assert TurboStreamDecoder().decode(text) == {"bad": None, "missing": None}

    def test_promise_without_id(self) -> None:
        """A malformed promise with no id is unresolved."""
        assert TurboStreamDecoder().decode('[["P"]]') is None


class TestErrors:
    """Malformed bodies raise RouvyResponseError."""

    @pytest.mark.parametrize(
        ("text", "match"),
        [
            ("", "Empty"),
            ("   \n  ", "Empty"),
            ("{not json", "Invalid JSON"),
            ("[]", "non-empty"),
            ('"just text"', "non-empty"),
            ("[1]\nX1:[2]", "prefix"),
            ("[1]\nP1", "prefix"),
            ("[[5]]", "out of range"),
            ('[{"_x":1}, 2]', "reference"),
            ("[[true]]", "reference"),
        ],
    )
    def test_malformed(self, text: str, match: str) -> None:
        """Each malformed input has a descriptive error."""
        with pytest.raises(RouvyResponseError, match=match):
            TurboStreamDecoder().decode(text)

    def test_too_deep(self) -> None:
        """Pathologically deep nesting is reported, not a crash."""
        depth = 5000
        values = ",".join(f"[{i + 1}]" for i in range(depth))

        with pytest.raises(RouvyResponseError, match="nested too deeply"):
            TurboStreamDecoder().decode(f"[{values},0]")


class TestRealCaptures:
    """Sanitized real Rouvy responses."""

    @pytest.mark.parametrize("fixture", sorted(FIXTURES_DIR.glob("*.txt")), ids=lambda p: p.name)
    def test_decodes(self, fixture: Path) -> None:
        """Every captured response decodes to a route map (pages) or a data object (actions)."""
        decoded = TurboStreamDecoder().decode(fixture.read_text(encoding="utf-8"))

        assert isinstance(decoded, dict)
        assert "root" in decoded or "data" in decoded
