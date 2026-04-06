# register-challenge

Register for a challenge

## Usage

```bash
rouvy-api register-challenge --slug <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--slug` | string | Yes | Unique slug identifier for the challenge |

## Examples

### Register for a challenge

```bash
rouvy-api register-challenge --slug summer-sprint-2025
```

#### Output

```json
{
  "status": "ok",
  "message": "Successfully registered for challenge 'summer-sprint-2025'"
}
```

## Output Schema

### WriteResponse

| Field | Type | Required |
| ----- | ---- | -------- |
| `status` | string | Yes |
| `message` | string | Yes |

---

*Stability: stable*
