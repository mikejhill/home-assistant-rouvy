# set-zones

Update training zones

## Usage

```bash
rouvy-api set-zones --type <value> --zones <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--type` | string | Yes | Zone type to update Choices: `power`, `heartRate` |
| `--zones` | string | Yes | Comma-separated zone boundary percentages |

## Examples

### Update power zones

```bash
rouvy-api set-zones --type power --zones 55,75,90,105,120
```

#### Output

```json
{
  "status": "ok",
  "message": "Power zones updated: 55,75,90,105,120"
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
