# set-weight

Update weight

## Usage

```bash
rouvy-api set-weight --weight <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--weight` | number | Yes | Weight in kilograms |

## Examples

### Set weight

```bash
rouvy-api set-weight --weight 75.5
```

#### Output

```json
{
  "status": "ok",
  "message": "Weight updated to 75.5 kg"
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
