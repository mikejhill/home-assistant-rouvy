# challenges

Display available challenges

## Usage

```bash
rouvy-api challenges
```

## Examples

### Display available challenges

```bash
rouvy-api challenges
```

#### Output

```json
[
  {
    "id": "ch-winter-warrior-2025",
    "user_status": "REGISTERED",
    "state": "ACTIVE",
    "registered_count": 14523,
    "registered": true,
    "title": "Winter Warrior 2025",
    "logo": "https://cdn.rouvy.com/challenges/winter-warrior-2025.png",
    "experience": 500,
    "coins": 250,
    "start_date_time": "2025-01-01T00:00:00Z",
    "end_date_time": "2025-02-28T23:59:59Z",
    "is_past": false,
    "is_upcoming": false,
    "is_done": false,
    "segments": []
  },
  {
    "id": "ch-alps-explorer",
    "user_status": "NOT_REGISTERED",
    "state": "UPCOMING",
    "registered_count": 3210,
    "registered": false,
    "title": "Alps Explorer",
    "logo": "https://cdn.rouvy.com/challenges/alps-explorer.png",
    "experience": 750,
    "coins": 400,
    "start_date_time": "2025-03-01T00:00:00Z",
    "end_date_time": "2025-04-30T23:59:59Z",
    "is_past": false,
    "is_upcoming": true,
    "is_done": false,
    "segments": []
  }
]
```

## Output Schema

### Challenges

| Field | Type | Required |
| ----- | ---- | -------- |
| `id` | string | Yes |
| `user_status` | string | Yes |
| `state` | string | Yes |
| `registered_count` | integer | Yes |
| `registered` | boolean | Yes |
| `title` | string | Yes |
| `logo` | string | Yes |
| `experience` | integer | Yes |
| `coins` | integer | Yes |
| `start_date_time` | string | Yes |
| `end_date_time` | string | Yes |
| `is_past` | boolean | Yes |
| `is_upcoming` | boolean | Yes |
| `is_done` | boolean | Yes |
| `segments` | array of object | Yes |

---

*Stability: stable*
