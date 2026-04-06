# profile

Display user profile

## Usage

```bash
rouvy-api profile
```

## Examples

### Display user profile

```bash
rouvy-api profile
```

#### Output

```json
{
  "email": "jan.novak@example.com",
  "username": "JanTheRider",
  "first_name": "Jan",
  "last_name": "Novak",
  "weight_kg": 78.5,
  "height_cm": 182.0,
  "units": "METRIC",
  "ftp_watts": 245,
  "ftp_source": "MANUAL",
  "max_heart_rate": 186,
  "gender": "MALE",
  "birth_date": "1988-03-15",
  "country": "CZ",
  "timezone": "Europe/Prague",
  "account_privacy": "PUBLIC",
  "user_id": "usr-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

## Output Schema

### UserProfile

| Field | Type | Required |
| ----- | ---- | -------- |
| `email` | string | Yes |
| `username` | string | Yes |
| `first_name` | string | Yes |
| `last_name` | string | Yes |
| `weight_kg` | number | Yes |
| `height_cm` | number | Yes |
| `units` | string | Yes |
| `ftp_watts` | integer | Yes |
| `ftp_source` | string | Yes |
| `max_heart_rate` | integer or null | No |
| `gender` | string or null | No |
| `birth_date` | string or null | No |
| `country` | string or null | No |
| `timezone` | string or null | No |
| `account_privacy` | string or null | No |
| `user_id` | string or null | No |

---

*Stability: stable*
