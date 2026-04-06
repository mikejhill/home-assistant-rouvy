# career

Display career statistics

## Usage

```bash
rouvy-api career
```

## Examples

### Display career statistics

```bash
rouvy-api career
```

#### Output

```json
{
  "total_distance_m": 2456780.0,
  "total_elevation_m": 34520.0,
  "total_time_seconds": 432000,
  "total_activities": 187,
  "total_achievements": 42,
  "total_trophies": 8,
  "experience_points": 12450,
  "level": 15,
  "coins": 3275
}
```

## Output Schema

### CareerStats

| Field | Type | Required |
| ----- | ---- | -------- |
| `total_distance_m` | number | Yes |
| `total_elevation_m` | number | Yes |
| `total_time_seconds` | integer | Yes |
| `total_activities` | integer | Yes |
| `total_achievements` | integer | Yes |
| `total_trophies` | integer | Yes |
| `experience_points` | integer | Yes |
| `level` | integer | Yes |
| `coins` | integer | Yes |

---

*Stability: stable*
