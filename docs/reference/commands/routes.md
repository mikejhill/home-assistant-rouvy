# routes

Display favorite routes

## Usage

```bash
rouvy-api routes
```

## Examples

### Display favorite routes

```bash
rouvy-api routes
```

#### Output

```json
[
  {
    "route_id": 10245,
    "name": "Col du Tourmalet",
    "distance_m": 42350.0,
    "elevation_m": 1268.0,
    "estimated_time_seconds": 5400,
    "rating": 4.7,
    "country_code": "FR",
    "favorite": true,
    "completed_distance_m": 42350.0,
    "online_count": 38,
    "coins_for_completion": 150
  },
  {
    "route_id": 8872,
    "name": "Mallorca Coastal Loop",
    "distance_m": 65200.0,
    "elevation_m": 780.0,
    "estimated_time_seconds": 7200,
    "rating": 4.5,
    "country_code": "ES",
    "favorite": true,
    "completed_distance_m": 0.0,
    "online_count": 15,
    "coins_for_completion": 200
  }
]
```

## Output Schema

### Routes

| Field | Type | Required |
| ----- | ---- | -------- |
| `route_id` | integer | Yes |
| `name` | string | Yes |
| `distance_m` | number | Yes |
| `elevation_m` | number | Yes |
| `estimated_time_seconds` | integer | Yes |
| `rating` | number | Yes |
| `country_code` | string | Yes |
| `favorite` | boolean | Yes |
| `completed_distance_m` | number | Yes |
| `online_count` | integer | Yes |
| `coins_for_completion` | integer | Yes |

---

*Stability: stable*
