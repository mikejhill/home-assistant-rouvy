# set-height

Update height

## Usage

```bash
rouvy-api set-height --height <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--height` | number | Yes | Height in centimeters |

## Examples

### Set height

```bash
rouvy-api set-height --height 180.5
```

#### Output

```json
{
  "status": "ok",
  "message": "Height updated to 180.5 cm"
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
