# events

Display upcoming events

## Usage

```bash
rouvy-api events
```

## Examples

### Display upcoming events

```bash
rouvy-api events
```

#### Output

```json
[
  {
    "event_id": "evt-sat-group-ride-2025-01-25",
    "title": "Saturday Group Ride",
    "event_type": "GROUP_RIDE",
    "start_date_time": "2025-01-25T09:00:00Z",
    "capacity": 100,
    "registered": true,
    "official": true,
    "coins_for_completion": 50,
    "experience": 100,
    "laps": 1
  },
  {
    "event_id": "evt-hill-climb-challenge-2025-01-27",
    "title": "Hill Climb Challenge",
    "event_type": "RACE",
    "start_date_time": "2025-01-27T18:30:00Z",
    "capacity": 50,
    "registered": false,
    "official": false,
    "coins_for_completion": 75,
    "experience": 150,
    "laps": 3
  }
]
```

## Output Schema

### Events

| Field | Type | Required |
| ----- | ---- | -------- |
| `event_id` | string | Yes |
| `title` | string | Yes |
| `event_type` | string | Yes |
| `start_date_time` | string | Yes |
| `capacity` | integer | Yes |
| `registered` | boolean | Yes |
| `official` | boolean | Yes |
| `coins_for_completion` | integer | Yes |
| `experience` | integer | Yes |
| `laps` | integer | Yes |

---

*Stability: stable*
