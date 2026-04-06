# zones

Display training zones

## Usage

```bash
rouvy-api zones
```

## Examples

### Display training zones

```bash
rouvy-api zones
```

#### Output

```json
{
  "ftp_watts": 245,
  "max_heart_rate": 186,
  "power_zone_values": [
    0,
    135,
    184,
    220,
    245,
    294,
    368
  ],
  "power_zone_defaults": [
    0,
    135,
    184,
    220,
    245,
    294,
    368
  ],
  "hr_zone_values": [
    0,
    112,
    130,
    149,
    167,
    186
  ],
  "hr_zone_defaults": [
    0,
    112,
    130,
    149,
    167,
    186
  ]
}
```

## Output Schema

### TrainingZones

| Field | Type | Required |
| ----- | ---- | -------- |
| `ftp_watts` | integer | Yes |
| `max_heart_rate` | integer | Yes |
| `power_zone_values` | array of integer | Yes |
| `power_zone_defaults` | array of integer | Yes |
| `hr_zone_values` | array of integer | Yes |
| `hr_zone_defaults` | array of integer | Yes |

---

*Stability: stable*
