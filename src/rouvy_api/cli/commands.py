"""Execution of CLI commands against a RouvyClient."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Final

from rouvy_api.cli.output import Formatter, Report
from rouvy_api.cli.settings import CommandArgs
from rouvy_api.client import RouvyClient
from rouvy_api.models import AccountPrivacy, FtpSource, UnitSystem, ZoneType

type Handler = Callable[[RouvyClient, CommandArgs], Awaitable[Report]]

_PROFILE_UNITS: Final = {
    "weight_kg": " kg",
    "height_cm": " cm",
    "ftp_watts": " W",
    "estimated_ftp_watts": " W",
    "max_heart_rate": " bpm",
}


class ReadCommands:
    """Handlers for commands that only read data."""

    @staticmethod
    async def login_check(client: RouvyClient, _args: CommandArgs) -> Report:
        """Log in and fetch the profile."""
        profile = await client.validate_credentials()
        name = profile.display_name or "unnamed rider"
        return Report(
            {"ok": True, "email": client.email}, [f"Logged in as {client.email} ({name})"]
        )

    @staticmethod
    async def profile(client: RouvyClient, _args: CommandArgs) -> Report:
        """Show the profile."""
        return Formatter.record(await client.get_user_profile(), units=_PROFILE_UNITS)

    @staticmethod
    async def zones(client: RouvyClient, _args: CommandArgs) -> Report:
        """Show zones."""
        zones = await client.get_training_zones()
        report = Formatter.record(zones, units=_PROFILE_UNITS)
        power = ", ".join(str(v) for v in zones.zones_for(ZoneType.POWER))
        heart = ", ".join(str(v) for v in zones.zones_for(ZoneType.HEART_RATE))
        return Report(
            report.data, [*report.lines, f"power zones (%)   {power}", f"heart zones (%)   {heart}"]
        )

    @staticmethod
    async def apps(client: RouvyClient, _args: CommandArgs) -> Report:
        """List connected apps."""
        apps = await client.get_connected_apps()
        return Formatter.items(
            list(apps), [Formatter.app(a) for a in apps], "No connected apps found."
        )

    @staticmethod
    async def overview(client: RouvyClient, _args: CommandArgs) -> Report:
        """Show period totals, career, and friends."""
        overview = await client.get_profile_overview()
        lines: list[str] = []
        for label, totals in (("month", overview.month_totals), ("year", overview.year_totals)):
            if totals is not None:
                lines.append(
                    f"{label:5}  {totals.distance_m / 1000:7.1f} km  {totals.ascent_m:6.0f} m  "
                    f"{totals.duration_s / 3600:5.1f} h"
                )
        if overview.career is not None:
            lines.append(
                f"career level {overview.career.level} ({overview.career.experience_points} XP)"
            )
        if overview.friends is not None:
            lines.append(f"friends {overview.friends.total} ({overview.friends.online} online)")
        return Report(overview.as_json(), lines or ["No overview data found."])

    @staticmethod
    async def activities(client: RouvyClient, _args: CommandArgs) -> Report:
        """List recent activities."""
        activities = list((await client.get_profile_overview()).recent_activities)
        lines = [Formatter.activity(a) for a in activities]
        return Formatter.items(list(activities), lines, "No activities found.")

    @staticmethod
    async def activity_stats(client: RouvyClient, args: CommandArgs) -> Report:
        """Show weekly totals for a month."""
        weeks = await client.get_weekly_activity_stats(args.year or 0, args.month or 0)
        return Formatter.items(
            list(weeks), [Formatter.week(w) for w in weeks], "No weekly stats found."
        )

    @staticmethod
    async def challenges(client: RouvyClient, _args: CommandArgs) -> Report:
        """List challenges."""
        items = await client.get_challenges()
        return Formatter.items(
            list(items), [Formatter.challenge(c) for c in items], "No challenges found."
        )

    @staticmethod
    async def routes(client: RouvyClient, args: CommandArgs) -> Report:
        """List routes."""
        items = await (client.get_favorite_routes() if args.favorites_only else client.get_routes())
        return Formatter.items(list(items), [Formatter.route(r) for r in items], "No routes found.")

    @staticmethod
    async def events(client: RouvyClient, _args: CommandArgs) -> Report:
        """List events."""
        items = await client.get_events()
        return Formatter.items(list(items), [Formatter.event(e) for e in items], "No events found.")

    @staticmethod
    async def achievements(client: RouvyClient, _args: CommandArgs) -> Report:
        """Show achievements."""
        return Formatter.record(await client.get_achievements())

    @staticmethod
    async def trophies(client: RouvyClient, _args: CommandArgs) -> Report:
        """Show trophies."""
        return Formatter.record(await client.get_trophies())

    @staticmethod
    async def raw(client: RouvyClient, args: CommandArgs) -> Report:
        """Print a decoded route as JSON (in both output modes)."""
        payload = await client.get_payload(args.text or "")
        data = Formatter.raw(payload.root)
        return Report(data, json.dumps(data, indent=2, ensure_ascii=False).splitlines())


class WriteCommands:
    """Handlers for commands that change account data."""

    @staticmethod
    async def set_weight(client: RouvyClient, args: CommandArgs) -> Report:
        """Set weight."""
        await client.update_body_metrics(weight_kg=args.number)
        return WriteCommands._done(f"Weight set to {args.number:g} kg")

    @staticmethod
    async def set_height(client: RouvyClient, args: CommandArgs) -> Report:
        """Set height."""
        await client.update_body_metrics(height_cm=args.number)
        return WriteCommands._done(f"Height set to {args.number:g} cm")

    @staticmethod
    async def set_units(client: RouvyClient, args: CommandArgs) -> Report:
        """Set the unit system."""
        await client.update_body_metrics(units=args.units or UnitSystem.METRIC)
        return WriteCommands._done(f"Units set to {args.units}")

    @staticmethod
    async def set_ftp(client: RouvyClient, args: CommandArgs) -> Report:
        """Set FTP."""
        if args.estimated:
            await client.update_ftp(FtpSource.ESTIMATED)
            return WriteCommands._done("FTP set to Rouvy's estimate")
        watts = round(args.number or 0)
        await client.update_ftp(FtpSource.MANUAL, watts)
        return WriteCommands._done(f"FTP set to {watts} W")

    @staticmethod
    async def set_max_hr(client: RouvyClient, args: CommandArgs) -> Report:
        """Set max heart rate."""
        bpm = round(args.number or 0)
        await client.update_max_heart_rate(bpm)
        return WriteCommands._done(f"Max heart rate set to {bpm} bpm")

    @staticmethod
    async def set_zones(client: RouvyClient, args: CommandArgs) -> Report:
        """Set zone boundaries."""
        zone_type = args.zone_type or ZoneType.POWER
        await client.update_zones(zone_type, args.zones)
        return WriteCommands._done(f"{zone_type} zones set to {', '.join(map(str, args.zones))}")

    @staticmethod
    async def set_timezone(client: RouvyClient, args: CommandArgs) -> Report:
        """Set timezone."""
        await client.update_timezone(args.text or "")
        return WriteCommands._done(f"Timezone set to {args.text}")

    @staticmethod
    async def set_privacy(client: RouvyClient, args: CommandArgs) -> Report:
        """Set account privacy."""
        await client.update_account_privacy(args.privacy or AccountPrivacy.PUBLIC)
        return WriteCommands._done(f"Account privacy set to {args.privacy}")

    @staticmethod
    async def set_profile(client: RouvyClient, args: CommandArgs) -> Report:
        """Change profile fields."""
        await client.update_profile(args.profile)
        return WriteCommands._done("Profile updated")

    @staticmethod
    async def register_challenge(client: RouvyClient, args: CommandArgs) -> Report:
        """Join a challenge."""
        await client.register_challenge(args.text or "")
        return WriteCommands._done(f"Joined challenge {args.text}")

    @staticmethod
    async def register_event(client: RouvyClient, args: CommandArgs) -> Report:
        """Join an event."""
        await client.register_event(args.text or "")
        return WriteCommands._done(f"Registered for event {args.text}")

    @staticmethod
    async def unregister_event(client: RouvyClient, args: CommandArgs) -> Report:
        """Leave an event."""
        await client.unregister_event(args.text or "")
        return WriteCommands._done(f"Unregistered from event {args.text}")

    @staticmethod
    def _done(message: str) -> Report:
        """Confirmation report for a write."""
        return Report({"ok": True, "message": message}, [message])


HANDLERS: Final[dict[str, Handler]] = {
    "login-check": ReadCommands.login_check,
    "profile": ReadCommands.profile,
    "zones": ReadCommands.zones,
    "apps": ReadCommands.apps,
    "overview": ReadCommands.overview,
    "activities": ReadCommands.activities,
    "activity-stats": ReadCommands.activity_stats,
    "challenges": ReadCommands.challenges,
    "routes": ReadCommands.routes,
    "events": ReadCommands.events,
    "achievements": ReadCommands.achievements,
    "trophies": ReadCommands.trophies,
    "raw": ReadCommands.raw,
    "set-weight": WriteCommands.set_weight,
    "set-height": WriteCommands.set_height,
    "set-units": WriteCommands.set_units,
    "set-ftp": WriteCommands.set_ftp,
    "set-max-hr": WriteCommands.set_max_hr,
    "set-zones": WriteCommands.set_zones,
    "set-timezone": WriteCommands.set_timezone,
    "set-privacy": WriteCommands.set_privacy,
    "set-profile": WriteCommands.set_profile,
    "register-challenge": WriteCommands.register_challenge,
    "register-event": WriteCommands.register_event,
    "unregister-event": WriteCommands.unregister_event,
}
