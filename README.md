# TrueNAS Chart Updater

Automatically update TrueNAS SCALE applications with a simple Docker container that works with both TrueNAS 24.04 (Dragonfish) and 25.04+ (Elastic Eel).

## Features

- Auto-detects TrueNAS version and uses the appropriate API
- Supports both REST API (for 24.04 and earlier) and WebSocket API (for 25.04+)
- Flexible scheduling options (cron or interval-based)
- Optional notifications via Apprise
- Lightweight container with minimal dependencies

## Usage

### Docker Run

```bash
docker run -e BASE_URL=https://truenas.local \
           -e API_KEY=your-api-key \
           -e CRON_SCHEDULE="0 2 * * *" \
           ghcr.io/regix1/truenas-chart-updater:latest
```

### Docker Compose

```yaml
version: '3'
services:
  chart-updater:
    image: ghcr.io/regix1/truenas-chart-updater:latest
    container_name: truenas-chart-updater
    environment:
      - BASE_URL=https://truenas.local
      - API_KEY=your-api-key
      - CRON_SCHEDULE=0 2 * * *  # Run at 2 AM daily
      # OR use interval-based scheduling instead:
      # - INTERVAL_SECONDS=3600  # Run every hour
      - APPRISE_URLS=telegram://bottoken/chatid  # Optional
      - NOTIFY_ON_SUCCESS=false  # Optional
    restart: unless-stopped
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BASE_URL` | URL of your TrueNAS instance | Yes |
| `API_KEY` | TrueNAS API key | Yes |
| `CRON_SCHEDULE` | Cron schedule expression (e.g., `0 2 * * *` for 2 AM daily) | No* |
| `INTERVAL_SECONDS` | Run every X seconds | No* |
| `APPRISE_URLS` | Comma-separated notification URLs for Apprise | No |
| `NOTIFY_ON_SUCCESS` | Set to "true" to notify on successful updates | No |
| `FORCE_WEBSOCKET` | Set to "true" to force using WebSocket API | No |

* At least one of `CRON_SCHEDULE` or `INTERVAL_SECONDS` is recommended, otherwise the script runs once and exits

## Scheduling Options

### Cron Schedule

Use standard cron syntax to run at specific times:

```
- CRON_SCHEDULE=0 2 * * *  # Run at 2 AM daily
```

### Interval-based

Run every X seconds:

```
- INTERVAL_SECONDS=86400  # Run every 24 hours
```

## Building Locally

```bash
git clone https://github.com/your-username/truenas-chart-updater.git
cd truenas-chart-updater
docker build -t truenas-chart-updater .
```

## License

MIT

## Disclaimer
This tool automatically updates your TrueNAS SCALE apps without manual intervention. While convenient, this could potentially lead to issues if an update introduces problems. Use at your own risk and make sure you have proper backups!

Cheers,  
[marvinvr](https://github.com/marvinvr)
