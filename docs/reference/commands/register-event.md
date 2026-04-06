# register-event

Register for an event

## Usage

```bash
rouvy-api register-event --event-id <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--event-id` | string | Yes | Unique event identifier |

## Examples

### Register for an event

```bash
rouvy-api register-event --event-id evt-abc123
```

#### Output

```json
{
  "status": "ok",
  "message": "Successfully registered for event 'evt-abc123'"
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
