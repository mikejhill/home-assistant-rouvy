# friends

Display friends summary

## Usage

```bash
rouvy-api friends
```

## Examples

### Display friends summary

```bash
rouvy-api friends
```

#### Output

```json
{
  "total_friends": 23,
  "online_friends": 4
}
```

## Output Schema

### FriendsSummary

| Field | Type | Required |
| ----- | ---- | -------- |
| `total_friends` | integer | Yes |
| `online_friends` | integer | Yes |

---

*Stability: stable*
