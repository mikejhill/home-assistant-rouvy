# activities

Display recent activities

## Usage

```bash
rouvy-api activities
```

## Examples

### Display recent activities

```bash
rouvy-api activities
```

#### Output

```json
[
  {
    "activity_id": "act-9f8e7d6c-5b4a-3210-fedc-ba9876543210",
    "title": "Col du Tourmalet",
    "start_utc": "2025-01-18T07:30:00Z",
    "training_type": "RIDE",
    "distance_m": 42350.0,
    "elevation_m": 1268.0,
    "moving_time_seconds": 5640,
    "intensity_factor": 0.82
  },
  {
    "activity_id": "act-1a2b3c4d-5e6f-7890-abcd-ef1234567890",
    "title": "Recovery Spin",
    "start_utc": "2025-01-17T18:00:00Z",
    "training_type": "WORKOUT",
    "distance_m": 15200.0,
    "elevation_m": 45.0,
    "moving_time_seconds": 1800,
    "intensity_factor": 0.55
  }
]
```

## Output Schema

### Activities

| Field | Type | Required |
| ----- | ---- | -------- |
| `activity_id` | string | Yes |
| `title` | string | Yes |
| `start_utc` | string or null | No |
| `training_type` | string | Yes |
| `distance_m` | number | Yes |
| `elevation_m` | number | Yes |
| `moving_time_seconds` | integer | Yes |
| `intensity_factor` | number or null | No |

---

*Stability: stable*
