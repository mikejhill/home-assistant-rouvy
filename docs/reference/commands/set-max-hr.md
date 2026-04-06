# set-max-hr

Update maximum heart rate

## Usage

```bash
rouvy-api set-max-hr --max-hr <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--max-hr` | integer | Yes | Maximum heart rate in bpm |

## Examples

### Set max heart rate

```bash
rouvy-api set-max-hr --max-hr 185
```

#### Output

```json
{
  "status": "ok",
  "message": "Max heart rate updated to 185 bpm"
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
