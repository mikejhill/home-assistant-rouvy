# apps

Display connected third-party apps

## Usage

```bash
rouvy-api apps
```

## Examples

### Display connected apps

```bash
rouvy-api apps
```

#### Output

```json
[
  {
    "provider_id": "strava",
    "name": "Strava",
    "status": "CONNECTED",
    "upload_mode": "AUTO",
    "description": "Automatically sync rides to Strava",
    "logo_path": "/images/apps/strava-logo.png",
    "permissions": [
      "activity_upload",
      "profile_read"
    ]
  },
  {
    "provider_id": "trainingpeaks",
    "name": "TrainingPeaks",
    "status": "DISCONNECTED",
    "upload_mode": null,
    "description": "Sync workouts with TrainingPeaks",
    "logo_path": "/images/apps/trainingpeaks-logo.png",
    "permissions": []
  }
]
```

## Output Schema

### ConnectedApps

| Field | Type | Required |
| ----- | ---- | -------- |
| `provider_id` | string | Yes |
| `name` | string | Yes |
| `status` | string | Yes |
| `upload_mode` | string or null | No |
| `description` | string or null | No |
| `logo_path` | string or null | No |
| `permissions` | array of string | No |

---

*Stability: stable*
