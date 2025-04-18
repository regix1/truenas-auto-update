# TrueNAS Auto Update

Automatically update TrueNAS SCALE applications with a simple Docker container that works with both TrueNAS 24.04 (Dragonfish) and 25.04+ (Elastic Eel).

## Features

- Auto-detects TrueNAS version and uses the appropriate API method
- Supports both REST API (for 24.04 and earlier) and WebSocket API (for 25.04+)
- Multiple authentication methods (API key or username/password)
- SSL configuration options with optional verification
- Flexible scheduling options (cron or interval-based)
- Enhanced logging with detailed TrueNAS system information
- Optional notifications via Apprise
- Lightweight container with minimal dependencies
- Cron schedule validation to prevent configuration errors

## Usage

### Docker Run

```bash
docker run -e BASE_URL=172.16.1.144 \
           -e API_KEY=your-api-key \
           -e USE_SSL=false \
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
      - API_KEY=your-api-key
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
| `BASE_URL` | Hostname or IP of your TrueNAS instance (without http/https prefix) | Yes |
| `API_KEY` | TrueNAS API key | Yes* |
| `USERNAME` | TrueNAS username (alternative to API_KEY) | No* |
| `PASSWORD` | TrueNAS password (required if using USERNAME) | No* |
| `USE_SSL` | Set to "true" to use HTTPS/WSS instead of HTTP/WS | No |
| `VERIFY_SSL` | Set to "true" to verify SSL certificates | No |
| `CRON_SCHEDULE` | Cron schedule expression (e.g., `0 2 * * *` for 2 AM daily) | No** |
| `INTERVAL_SECONDS` | Run every X seconds | No** |
| `APPRISE_URLS` | Comma-separated notification URLs for Apprise | No |
| `NOTIFY_ON_SUCCESS` | Set to "true" to notify on successful updates | No |
| `TZ` | Timezone for container (e.g., `America/Chicago`) | No |

* Either `API_KEY` or both `USERNAME` and `PASSWORD` must be provided
** At least one of `CRON_SCHEDULE` or `INTERVAL_SECONDS` is recommended, otherwise the script runs once and exits

## Authentication Options

You can authenticate using either:

1. **API Key** (recommended):
   ```
   - API_KEY=your-api-key
   ```
   
2. **Username and Password**:
   ```
   - USERNAME=admin
   - PASSWORD=your-password
   ```

## SSL Configuration

For secure connections:

```
- USE_SSL=true      # Use HTTPS/WSS instead of HTTP/WS
- VERIFY_SSL=true   # Verify SSL certificates (set to false for self-signed certs)
```

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
3. API connection status and type (REST or WebSocket)
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
2. The API_KEY or USERNAME/PASSWORD has the proper permissions
3. Network connectivity between the container and TrueNAS
4. SSL settings are correct if your TrueNAS uses HTTPS

### Version Detection Issues

If you're having trouble with automatic version detection:
1. Make sure your TrueNAS is accessible at the configured BASE_URL
2. Check if you need to use SSL (`USE_SSL=true`) for your setup
3. Ensure your authentication credentials have sufficient permissions

## Building Locally

```bash
git clone https://github.com/regix1/truenas-auto-update.git
cd truenas-auto-update
docker build -t truenas-auto-update .
```

## License

MIT

## Disclaimer
Message from the original developer:
This tool automatically updates your TrueNAS SCALE apps without manual intervention. While convenient, this could potentially lead to issues if an update introduces problems. Use at your own risk and make sure you have proper backups!

Cheers,
[marvinvr](https://github.com/marvinvr)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
