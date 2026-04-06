# set-profile

Update profile fields

## Usage

```bash
rouvy-api set-profile [--username <value>] [--first-name <value>] [--last-name <value>] [--team <value>] [--country <value>] [--privacy <value>]
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--username` | string | No | Username |
| `--first-name` | string | No | First name |
| `--last-name` | string | No | Last name |
| `--team` | string | No | Team name |
| `--country` | string | No | Country code |
| `--privacy` | string | No | Account privacy setting Choices: `PUBLIC`, `PRIVATE` |

## Examples

### Update username and country

```bash
rouvy-api set-profile --username rider42 --country CZ
```

#### Output

```json
{
  "status": "ok",
  "message": "Profile updated: username=rider42, country=CZ"
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
