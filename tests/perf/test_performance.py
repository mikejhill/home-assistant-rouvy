"""Performance budgets and benchmarks for decoding, parsing, and fetching."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from rouvy_api import Endpoint, Payload, RouvyClient, TurboStreamDecoder
from rouvy_api.parsers import RouvyParser
from tests.support.fake_rouvy import FakeRouvy
from tests.support.rouvy_payloads import FIXTURES_DIR, RouvyPayloads
from tests.support.turbo_encoder import Deferred, EncodedValue, TurboStreamEncoder

pytestmark = pytest.mark.perf


class Workloads:
    """Inputs for performance tests."""

    @staticmethod
    def large_payload(activities: int = 2500) -> str:
        """Return a ~50k-value payload shaped like an activity history page."""
        items: list[EncodedValue] = [
            {
                "id": f"activity-{i}",
                "title": f"Route {i % 400}",
                "startUTC": f"2026-01-{i % 28 + 1:02d}T07:00:00.000Z",
                "training": "ROUTE",
                "total": {
                    "distM": 1000.5 * i,
                    "elevM": i % 900,
                    "kCal": i,
                    "movingTimeSec": 60 * i,
                },
                "trainingScore": i % 120,
            }
            for i in range(activities)
        ]
        return TurboStreamEncoder().encode(
            {
                "routes/_main": {"data": {"friendsPromise": Deferred({"total": 3})}},
                "page": {"activities": Deferred(items)},
            }
        )

    @staticmethod
    def fixtures() -> list[str]:
        """Return every sanitized capture."""
        return [p.read_text(encoding="utf-8") for p in sorted(FIXTURES_DIR.glob("*.txt"))]

    @staticmethod
    def best_of(runs: int, action: Callable[[], object]) -> float:
        """Return the fastest wall time of several runs, in seconds."""
        timings = []
        for _ in range(runs):
            started = time.perf_counter()
            action()
            timings.append(time.perf_counter() - started)
        return min(timings)


@pytest.fixture(scope="module")
def large_payload() -> str:
    """The large synthetic payload."""
    return Workloads.large_payload()


class TestBudgets:
    """Hard limits that fail CI on regressions."""

    def test_large_payload_decodes_quickly(self, large_payload: str) -> None:
        """A ~50k-value payload decodes in under half a second."""
        elapsed = Workloads.best_of(5, lambda: TurboStreamDecoder().decode(large_payload))

        assert elapsed < 0.5, f"decode took {elapsed:.3f}s"

    def test_fixtures_decode_quickly(self) -> None:
        """All real captures decode in under 100 ms in total."""
        texts = Workloads.fixtures()

        elapsed = Workloads.best_of(5, lambda: [TurboStreamDecoder().decode(t) for t in texts])

        assert elapsed < 0.1, f"decode took {elapsed:.3f}s"

    def test_parse_large_activity_list(self, large_payload: str) -> None:
        """Parsing 2,500 activities takes under half a second."""
        parser = RouvyParser()

        elapsed = Workloads.best_of(3, lambda: parser.activities(Payload.parse(large_payload)))

        assert elapsed < 0.5, f"parse took {elapsed:.3f}s"

    async def test_reads_run_concurrently(
        self, rouvy_client: RouvyClient, fake_rouvy: FakeRouvy
    ) -> None:
        """Eight reads with 200 ms latency each finish in about one round trip, not eight."""
        await rouvy_client.login()
        fake_rouvy.state.latency_s = 0.2

        started = time.perf_counter()
        await asyncio.gather(
            rouvy_client.get_user_profile(),
            rouvy_client.get_training_zones(),
            rouvy_client.get_connected_apps(),
            rouvy_client.get_profile_overview(),
            rouvy_client.get_challenges(),
            rouvy_client.get_events(),
            rouvy_client.get_achievements(),
            rouvy_client.get_trophies(),
        )
        elapsed = time.perf_counter() - started

        assert elapsed < 1.0, f"8 reads took {elapsed:.3f}s"


class TestBenchmarks:
    """Benchmarks recorded in CI (pytest-benchmark)."""

    @pytest.mark.parametrize("endpoint", [Endpoint.USER_SETTINGS, Endpoint.PROFILE_OVERVIEW])
    def test_decode_capture(
        self, benchmark: BenchmarkFixture, payloads: RouvyPayloads, endpoint: str
    ) -> None:
        """Decode a real capture."""
        text = payloads.captured(endpoint)

        result = benchmark(lambda: TurboStreamDecoder().decode(text))

        assert isinstance(result, dict)

    def test_decode_large(self, benchmark: BenchmarkFixture, large_payload: str) -> None:
        """Decode the large synthetic payload."""
        result = benchmark(lambda: TurboStreamDecoder().decode(large_payload))

        assert isinstance(result, dict)

    def test_parse_overview(self, benchmark: BenchmarkFixture, payloads: RouvyPayloads) -> None:
        """Decode and parse the profile overview."""
        text = payloads.captured(Endpoint.PROFILE_OVERVIEW)
        parser = RouvyParser()

        overview = benchmark(lambda: parser.profile_overview(Payload.parse(text)))

        assert len(overview.recent_activities) == 10

    def test_find_in_large_payload(self, benchmark: BenchmarkFixture, large_payload: str) -> None:
        """Breadth-first search for a key that does not exist (worst case)."""
        payload = Payload.parse(large_payload)

        assert benchmark(lambda: payload.find("not-present")) is None
