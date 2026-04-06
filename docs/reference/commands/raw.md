# raw

Fetch a raw API endpoint

## Usage

```bash
rouvy-api raw <endpoint>
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `endpoint` | string | Yes | API endpoint path to fetch |

## Examples

### Fetch raw user endpoint

```bash
rouvy-api raw /api/v2/user
```

#### Output

```json
{
  "endpoint": "/api/v2/user",
  "data": {
    "id": "usr-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "attributes": {
      "username": "JanTheRider",
      "email": "jan.novak@example.com"
    }
  }
}
```

## Output Schema

### RawResponse

| Field | Type | Required |
| ----- | ---- | -------- |

## Notes

- Output structure varies depending on the endpoint queried

---

*Stability: stable*
