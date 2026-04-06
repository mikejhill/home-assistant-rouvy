# activity-stats

Display weekly activity statistics for a given month

## Usage

```bash
rouvy-api activity-stats --year <value> --month <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--year` | int | Yes | Calendar year to query |
| `--month` | int | Yes | Calendar month to query (1-12) |

## Examples

### Display weekly stats for January 2025

```bash
rouvy-api activity-stats --year 2025 --month 1
```

#### Output

```json
[
  {
    "week_start": "2025-01-06",
    "week_end": "2025-01-12",
    "ride": {
      "distance_m": 128500.0,
      "elevation_m": 1850.0,
      "calories": 3200.0,
      "moving_time_seconds": 14400,
      "intensity_factor": 0.75,
      "training_score": 245.0,
      "activity_count": 4
    },
    "workout": {
      "distance_m": 22000.0,
      "elevation_m": 0.0,
      "calories": 580.0,
      "moving_time_seconds": 3600,
      "intensity_factor": 0.65,
      "training_score": 52.0,
      "activity_count": 2
    },
    "event": {
      "distance_m": 45000.0,
      "elevation_m": 620.0,
      "calories": 1100.0,
      "moving_time_seconds": 5400,
      "intensity_factor": 0.88,
      "training_score": 110.0,
      "activity_count": 1
    },
    "outdoor": {
      "distance_m": 0.0,
      "elevation_m": 0.0,
      "calories": 0.0,
      "moving_time_seconds": 0,
      "intensity_factor": 0.0,
      "training_score": 0.0,
      "activity_count": 0
    }
  },
  {
    "week_start": "2025-01-13",
    "week_end": "2025-01-19",
    "ride": {
      "distance_m": 95000.0,
      "elevation_m": 1420.0,
      "calories": 2400.0,
      "moving_time_seconds": 10800,
      "intensity_factor": 0.72,
      "training_score": 185.0,
      "activity_count": 3
    },
    "workout": {
      "distance_m": 0.0,
      "elevation_m": 0.0,
      "calories": 0.0,
      "moving_time_seconds": 0,
      "intensity_factor": 0.0,
      "training_score": 0.0,
      "activity_count": 0
    },
    "event": {
      "distance_m": 0.0,
      "elevation_m": 0.0,
      "calories": 0.0,
      "moving_time_seconds": 0,
      "intensity_factor": 0.0,
      "training_score": 0.0,
      "activity_count": 0
    },
    "outdoor": {
      "distance_m": 35000.0,
      "elevation_m": 480.0,
      "calories": 850.0,
      "moving_time_seconds": 4200,
      "intensity_factor": 0.68,
      "training_score": 72.0,
      "activity_count": 1
    }
  }
]
```

## Output Schema

### WeeklyActivityStats

| Field | Type | Required |
| ----- | ---- | -------- |
| `week_start` | string | Yes |
| `week_end` | string | Yes |
| `ride` | ActivityTypeStats | Yes |
| `workout` | ActivityTypeStats | Yes |
| `event` | ActivityTypeStats | Yes |
| `outdoor` | ActivityTypeStats | Yes |

---

*Stability: stable*
