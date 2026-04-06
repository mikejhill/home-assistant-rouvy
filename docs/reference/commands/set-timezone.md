# set-timezone

Update timezone

## Usage

```bash
rouvy-api set-timezone --timezone <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--timezone` | string | Yes | IANA timezone identifier |

## Examples

### Set timezone

```bash
rouvy-api set-timezone --timezone Europe/Prague
```

#### Output

```json
{
  "status": "ok",
  "message": "Timezone updated to Europe/Prague"
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
