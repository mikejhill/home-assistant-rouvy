# Schema Reference

JSON Schema definitions for all CLI output types. These schemas define the
structure of `--json` output from each command.

Schema source files are located in
[`docs-src/schemas/`](https://github.com/mikejhill/home-assistant-rouvy/tree/main/docs-src/schemas)
in the repository.

## Response Models

| Schema | Used By | Description |
|--------|---------|-------------|
| `profile.response.schema.json` | `profile` | User profile data |
| `zones.response.schema.json` | `zones` | Training zone config |
| `activities.response.schema.json` | `activities` | Recent activities |
| `activity-stats.response.schema.json` | `activity-stats` | Weekly stats |
| `apps.response.schema.json` | `apps` | Connected apps |
| `career.response.schema.json` | `career` | Career progression |
| `challenges.response.schema.json` | `challenges` | Challenges |
| `events.response.schema.json` | `events` | Upcoming events |
| `friends.response.schema.json` | `friends` | Friends summary |
| `routes.response.schema.json` | `routes` | Favorite routes |
| `write-response.schema.json` | Write commands | Success/failure |

## Schema Format

All schemas use [JSON Schema draft 2020-12](https://json-schema.org/draft/2020-12/schema).
Schemas are validated in CI and used to verify example output files.

## Using Schemas

Schemas can be used to validate CLI output programmatically:

```bash
# Pipe JSON output through a schema validator
rouvy-api profile --json | ajv validate -s docs-src/schemas/profile.response.schema.json
```
