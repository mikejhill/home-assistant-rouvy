# CLI Command Reference

The `rouvy-api` CLI provides 23 subcommands for interacting with the Rouvy
API. All commands support `--json` for machine-readable output.

## Read Commands

| Command | Description |
|---------|-------------|
| [`profile`](profile.md) | Display user profile (default) |
| [`zones`](zones.md) | Display training zones |
| [`activities`](activities.md) | Display recent activities |
| [`activity-stats`](activity-stats.md) | Weekly activity statistics |
| [`apps`](apps.md) | Display connected apps |
| [`career`](career.md) | Career progression stats |
| [`challenges`](challenges.md) | List available challenges |
| [`events`](events.md) | List upcoming events |
| [`friends`](friends.md) | Friends summary |
| [`routes`](routes.md) | List favorite routes |
| [`raw`](raw.md) | Fetch raw decoded turbo-stream response |

## Write Commands

| Command | Description |
|---------|-------------|
| [`set`](set.md) | Update user settings (KEY=VALUE pairs) |
| [`set-ftp`](set-ftp.md) | Update FTP |
| [`set-height`](set-height.md) | Update height |
| [`set-max-hr`](set-max-hr.md) | Update max heart rate |
| [`set-profile`](set-profile.md) | Update profile fields |
| [`set-timezone`](set-timezone.md) | Update timezone |
| [`set-units`](set-units.md) | Update units |
| [`set-weight`](set-weight.md) | Update weight |
| [`set-zones`](set-zones.md) | Update zone boundaries |
| [`register-challenge`](register-challenge.md) | Register for a challenge |
| [`register-event`](register-event.md) | Register for an event |
| [`unregister-event`](unregister-event.md) | Unregister from an event |

## Global Flags

All commands support:

```text
--json              Output as JSON instead of formatted text
--verbose           Enable debug logging (shortcut for --log-level DEBUG)
--log-level LEVEL   Set log level (DEBUG, INFO, WARNING, ERROR)
```
