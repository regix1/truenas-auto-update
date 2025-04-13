#!/bin/bash
set -e

# Check which scheduling method to use
if [ -n "$CRON_SCHEDULE" ]; then
    echo "Setting up cron with schedule: $CRON_SCHEDULE"
    
    # Create a cron file with the provided schedule
    cat <<EOF > /etc/cron.d/app-cron
$CRON_SCHEDULE cd /app && python app.py >> /var/log/cron.log 2>&1
# Empty line is required for valid cron file
EOF
    
    # Set proper permissions
    chmod 0644 /etc/cron.d/app-cron
    crontab /etc/cron.d/app-cron
    
    # Export environment variables for cron jobs
    printenv | grep -v "no_proxy" > /etc/environment
    
    # Start cron service and tail the log
    service cron start
    echo "Cron job installed with schedule: $CRON_SCHEDULE"
    echo "Watching logs..."
    tail -f /var/log/cron.log
    
elif [ -n "$INTERVAL_SECONDS" ]; then
    echo "Running in interval mode every $INTERVAL_SECONDS seconds"
    
    while true; do
        echo "Starting chart update check at $(date)"
        python app.py
        echo "Finished update check, sleeping for $INTERVAL_SECONDS seconds"
        sleep $INTERVAL_SECONDS
    done
    
else
    echo "Running once (no scheduling configured)"
    exec python app.py
fi