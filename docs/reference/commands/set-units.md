# set-units

Update measurement units

## Usage

```bash
rouvy-api set-units --units <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--units` | string | Yes | Measurement unit system Choices: `METRIC`, `IMPERIAL` |

## Examples

### Set units to metric

```bash
rouvy-api set-units --units METRIC
```

#### Output

```json
{
  "status": "ok",
  "message": "Units updated to METRIC"
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
