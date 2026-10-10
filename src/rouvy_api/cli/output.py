"""Human-readable and JSON rendering of command results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TextIO

from rouvy_api.models import (
    Activity,
    Challenge,
    ConnectedApp,
    Event,
    JsonExportable,
    JsonValue,
    Route,
    WeeklyActivityStats,
)
from rouvy_api.turbo_stream import TaggedValue, TurboValue


@dataclass(frozen=True, slots=True)
class Report:
    """A command result: JSON data plus its human-readable lines."""

    data: JsonValue
    lines: list[str] = field(default_factory=list)


class Formatter:
    """Build Reports from models."""

    @staticmethod
    def record(model: JsonExportable, *, units: dict[str, str] | None = None) -> Report:
        """Render one model as aligned ``key: value`` lines."""
        data = model.as_json()
        width = max((len(key) for key in data), default=0)
        lines = [
            f"{key.ljust(width)}  {Formatter.value(value)}{(units or {}).get(key, '')}"
            for key, value in data.items()
            if not isinstance(value, dict | list)
        ]
        return Report(data, lines)

    @staticmethod
    def items(models: list[JsonExportable], lines: list[str], empty: str) -> Report:
        """Render a list of models with one line each."""
        return Report([m.as_json() for m in models], lines or [empty])

    @staticmethod
    def value(value: JsonValue) -> str:
        """Render a scalar for humans."""
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, float):
            return f"{value:.1f}"
        return str(value)

    @staticmethod
    def when(moment: datetime | None) -> str:
        """Render a timestamp in local time, minute precision."""
        return moment.astimezone().strftime("%Y-%m-%d %H:%M") if moment else "----------  --:--"

    @staticmethod
    def event(event: Event) -> str:
        """One line per event."""
        flag = "  [registered]" if event.registered else ""
        return f"{Formatter.when(event.starts_at)}  {event.title or event.event_id}{flag}"

    @staticmethod
    def activity(activity: Activity) -> str:
        """One line per activity."""
        return (
            f"{Formatter.when(activity.started_at)}  {activity.distance_m / 1000:6.1f} km  "
            f"{activity.moving_time_s / 60:5.0f} min  {activity.title or activity.training_type}"
        )

    @staticmethod
    def challenge(challenge: Challenge) -> str:
        """One line per challenge."""
        status = "done" if challenge.is_done else "joined" if challenge.registered else "open"
        return (
            f"{status:6}  {challenge.title or challenge.challenge_id}  ({challenge.challenge_id})"
        )

    @staticmethod
    def route(route: Route) -> str:
        """One line per route."""
        star = "*" if route.favorite else " "
        return (
            f"{star} {route.route_id:>7}  {route.distance_m / 1000:6.1f} km  "
            f"{route.elevation_m:5.0f} m  {route.name or '-'}"
        )

    @staticmethod
    def app(app: ConnectedApp) -> str:
        """One line per connected app."""
        return f"{app.status:16}  {app.name}"

    @staticmethod
    def week(week: WeeklyActivityStats) -> str:
        """One line per week (all activity types)."""
        parts = (week.ride, week.workout, week.event, week.outdoor)
        distance = sum(p.distance_m for p in parts) / 1000
        minutes = sum(p.moving_time_s for p in parts) / 60
        count = sum(p.activity_count for p in parts)
        span = f"{week.week_start} .. {week.week_end}"
        return f"{span}  {count:2} rides  {distance:6.1f} km  {minutes:5.0f} min"

    @staticmethod
    def raw(value: TurboValue) -> JsonValue:
        """Convert a decoded payload into JSON-compatible data."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, TaggedValue):
            return {"tag": value.tag, "args": [Formatter.raw(a) for a in value.args]}
        if isinstance(value, list):
            return [Formatter.raw(v) for v in value]
        if isinstance(value, dict):
            return {k: Formatter.raw(v) for k, v in value.items()}
        return value


class OutputWriter:
    """Write Reports to a stream as text or JSON."""

    def __init__(self, stream: TextIO, *, as_json: bool) -> None:
        self._stream = stream
        self._as_json = as_json

    def write(self, report: Report) -> None:
        """Write one report."""
        if self._as_json:
            self._stream.write(json.dumps(report.data, indent=2, ensure_ascii=False) + "\n")
            return
        self._stream.write("".join(f"{line}\n" for line in report.lines))
