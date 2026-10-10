"""Property-based tests for the turbo-stream decoder and payload accessors."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from rouvy_api import Fields, Payload, RouvyResponseError, TurboStreamDecoder, TurboValue
from tests.support.turbo_encoder import Deferred, EncodedValue, TurboStreamEncoder

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
dates = st.integers(min_value=0, max_value=4_102_444_800_000).map(
    lambda ms: EPOCH + timedelta(milliseconds=ms)
)
scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**53), max_value=2**53)
    | st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: f != 0 or str(f) == "0.0")
    | st.text(max_size=20)
    | dates
)
trees = st.recursive(
    scalars,
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(st.text(max_size=10), children, max_size=5)
        | children.map(Deferred)
    ),
    max_leaves=40,
)


class Unwrap:
    """Remove Deferred wrappers to get the value a decoder should produce."""

    @staticmethod
    def value(tree: EncodedValue) -> TurboValue:
        """Return the tree with every Deferred replaced by its value."""
        if isinstance(tree, Deferred):
            return Unwrap.value(tree.value)
        if isinstance(tree, list):
            return [Unwrap.value(item) for item in tree]
        if isinstance(tree, dict):
            return {key: Unwrap.value(item) for key, item in tree.items()}
        return tree  # ty: ignore[invalid-return-type]  # remaining leaves are TurboValue scalars


class TestRoundTrip:
    """encode -> decode is lossless."""

    @settings(max_examples=300, deadline=None)
    @given(trees)
    def test_roundtrip(self, tree: EncodedValue) -> None:
        """Any JSON-like tree with dates and deferred promises survives a round trip."""
        text = TurboStreamEncoder().encode(tree)

        assert TurboStreamDecoder().decode(text) == Unwrap.value(tree)

    @settings(max_examples=100, deadline=None)
    @given(st.dictionaries(st.text(max_size=8), trees, min_size=1, max_size=5))
    def test_find_returns_a_top_level_value(self, tree: dict[str, EncodedValue]) -> None:
        """find() on a top-level key returns that key's value (it is the shallowest)."""
        payload = Payload.parse(TurboStreamEncoder().encode(tree))
        key = next(iter(tree))

        assert payload.find(key) == Unwrap.value(tree[key])


class TestRobustness:
    """Arbitrary input never crashes with an unexpected exception."""

    @settings(max_examples=300, deadline=None)
    @given(st.text(max_size=200))
    def test_decoder_only_raises_response_errors(self, text: str) -> None:
        """Garbage text raises RouvyResponseError or decodes; nothing else escapes."""
        with contextlib.suppress(RouvyResponseError):
            TurboStreamDecoder().decode(text)

    @settings(max_examples=300, deadline=None)
    @given(
        st.lists(
            st.none() | st.booleans() | st.integers(-10, 10) | st.text(max_size=3), max_size=8
        ).map(lambda items: "[" + ",".join(Fuzz.json(i) for i in items) + "]")
    )
    def test_decoder_on_random_flat_arrays(self, text: str) -> None:
        """Random flat arrays with dangling references fail cleanly."""
        with contextlib.suppress(RouvyResponseError):
            TurboStreamDecoder().decode(text)

    @settings(max_examples=200, deadline=None)
    @given(trees)
    def test_fields_accessors_never_raise(self, tree: EncodedValue) -> None:
        """Every accessor tolerates any value type."""
        fields = Fields({"k": Unwrap.value(tree)})

        fields.text("k")
        fields.integer("k")
        fields.number("k")
        fields.flag("k")
        fields.mapping("k")
        fields.records("k")
        fields.numbers("k")
        fields.strings("k")
        fields.timestamp("k")
        fields.day("k")


class Fuzz:
    """Helpers for building fuzz input."""

    @staticmethod
    def json(value: bool | int | str | None) -> str:
        """Render a scalar as a JSON token."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
