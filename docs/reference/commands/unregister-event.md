# unregister-event

Unregister from an event

## Usage

```bash
rouvy-api unregister-event --event-id <value>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--event-id` | string | Yes | Unique event identifier |

## Examples

### Unregister from an event

```bash
rouvy-api unregister-event --event-id evt-abc123
```

#### Output

```json
{
  "status": "ok",
  "message": "Successfully unregistered from event 'evt-abc123'"
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
