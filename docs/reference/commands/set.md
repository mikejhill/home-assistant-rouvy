# set

Update one or more settings

## Usage

```bash
rouvy-api set <settings>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `settings` | string | Yes | One or more KEY=VALUE pairs to update |

## Examples

### Update multiple settings

```bash
rouvy-api set units=METRIC weight_kg=75.0
```

#### Output

```json
{
  "status": "ok",
  "message": "Updated settings: units=METRIC, weight_kg=75.0"
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
