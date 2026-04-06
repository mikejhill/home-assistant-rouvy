# set-ftp

Update FTP setting

## Usage

```bash
rouvy-api set-ftp --source <value> [--value <value>]
```

## Arguments

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--source` | string | Yes | FTP source type Choices: `MANUAL`, `ESTIMATED` |
| `--value` | integer | No | FTP value in watts |

## Examples

### Set FTP manually

```bash
rouvy-api set-ftp --source MANUAL --value 220
```

#### Output

```json
{
  "status": "ok",
  "message": "FTP updated to 220 watts (source: MANUAL)"
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
