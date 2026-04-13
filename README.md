# Busch Light Apple NJ Monitor

Checks every NJ zip code every 5 minutes for Busch Light Apple availability via the busch.com store locator API. Sends a push notification via [ntfy.sh](https://ntfy.sh) when stores are found.

## How it works

- Deployed as a scheduled Claude Code remote agent (runs hourly)
- Each agent session runs 11 scans × 5-minute intervals = 55 minutes of coverage
- Uses the `api.beertech.com` GraphQL API (same one the busch.com locator uses)
- Notifications go to ntfy.sh topic `busch-apple-nj`

## Receiving notifications

1. Install the [ntfy app](https://ntfy.sh) on your phone (iOS or Android — free)
2. Subscribe to topic: `busch-apple-nj`
3. Done — you'll get a push notification the moment any NJ store has stock

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NTFY_TOPIC` | `busch-apple-nj` | ntfy.sh topic to publish to |

## Running locally

```bash
pip install -r requirements.txt
python monitor.py
```
