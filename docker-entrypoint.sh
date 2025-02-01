#!/bin/bash
set -e

if [ -n "$CRON_SCHEDULE" ]; then
    echo "Setting up cron with schedule: $CRON_SCHEDULE"

    # Create a cron file on the fly with environment variables passed along
    cat <<EOF > /etc/cron.d/app-cron
$CRON_SCHEDULE cd /app && /usr/local/bin/python main.py >> /var/log/cron.log 2>&1
EOF

    chmod 0644 /etc/cron.d/app-cron
    crontab /etc/cron.d/app-cron

    # Export environment variables for cron jobs (exclude no_proxy if necessary)
    printenv | grep -v "no_proxy" >> /etc/environment

    # Start cron service and tail the log
    service cron start
    echo "Cron job installed. Watching logs..."
    tail -f /var/log/cron.log
else
    echo "No CRON_SCHEDULE set, running script once..."
    exec python main.py
fi
