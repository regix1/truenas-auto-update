# TrueNAS Auto Update

Automatically update TrueNAS SCALE applications with a simple Docker container that works with both TrueNAS 24.04 (Dragonfish) and 25.04+ (Elastic Eel).

## Features

- Auto-detects TrueNAS version and uses the appropriate API
- Supports both REST API (for 24.04 and earlier) and WebSocket API (for 25.04+)
- Flexible scheduling options (cron or interval-based)
- Enhanced logging with detailed TrueNAS system information
- Optional notifications via Apprise
- Lightweight container with minimal dependencies
- Cron schedule validation to prevent configuration errors

## Usage

### Docker Run

```bash
docker run -e BASE_URL=https://truenas.local \
           -e API_KEY=your-api-key \
           -e CRON_SCHEDULE="0 2 * * *" \
           -e TZ=America/Chicago \
           ghcr.io/regix1/truenas-auto-update:latest
```

### Docker Compose

```yaml
version: '3'
services:
  truenas-auto-update:
    container_name: truenas-auto-update
    image: ghcr.io/regix1/truenas-auto-update
    environment:
      - BASE_URL=172.16.1.144
      - API_KEY=1-GtF52L9uraHfHM2j4774DrsrMdckHOjyjMBWv1e6AlEEUXbVzwG3eq8LnQapq4vJ
      # Alternative authentication method (only needed if not using API_KEY)
      # - USERNAME=admin
      # - PASSWORD=your_password
      # SSL settings
      - USE_SSL=false
      - VERIFY_SSL=false
      # Update schedule
      # - CRON_SCHEDULE=0 5 * * *
      - INTERVAL_SECONDS=30
      # Notification settings
      - NOTIFY_ON_SUCCESS=true
      # Optional notification methods (if configured)
      # - APPRISE_URLS=telegram://bot_token/chat_id
      # Timezone
      - TZ=America/Chicago
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
| `TZ` | Timezone for container (e.g., `America/Chicago`) | No |

* At least one of `CRON_SCHEDULE` or `INTERVAL_SECONDS` is recommended, otherwise the script runs once and exits

## Scheduling Options

### Cron Schedule

Use standard cron syntax to run at specific times:

```
- CRON_SCHEDULE=0 2 * * *  # Run at 2 AM daily
```

The script validates your cron schedule to ensure it has exactly 5 fields separated by spaces. An invalid schedule will prevent the container from starting.

### Interval-based

Run every X seconds:

```
- INTERVAL_SECONDS=86400  # Run every 24 hours
```

## Logs and Information

When the container starts, it will display:

1. Container start time and timezone
2. TrueNAS system information (hostname and version)
3. API connection status
4. Cron schedule validation

To view logs:

```bash
docker logs truenas-auto-update
```

## Troubleshooting

### Invalid Cron Schedule

If you see an error like:
```
ERROR: Invalid cron schedule format: '0 5 * **'
ERROR: Cron schedule must have exactly 5 fields (minute hour day month weekday)
```

Make sure your cron schedule has proper spacing between all fields, for example:
```
0 5 * * *
```

### API Connection Issues

If the container can't connect to your TrueNAS instance, check:
1. The BASE_URL is correct and accessible
2. The API_KEY has the proper permissions
3. Network connectivity between the container and TrueNAS

## Building Locally

```bash
git clone https://github.com/regix1/truenas-auto-update.git
cd truenas-auto-update
docker build -t truenas-auto-update .
```

## License

MIT

## Disclaimer
This tool automatically updates your TrueNAS SCALE apps without manual intervention. While convenient, this could potentially lead to issues if an update introduces problems. Use at your own risk and make sure you have proper backups!

Cheers,  
[marvinvr](https://github.com/marvinvr)
