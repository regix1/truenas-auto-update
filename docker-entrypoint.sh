#!/bin/bash
set -e

# Function to validate cron schedule
validate_cron_schedule() {
    local schedule="$1"
    
    # Count the fields (should be 5)
    field_count=$(echo "$schedule" | awk '{print NF}')
    
    if [[ $field_count -ne 5 ]]; then
        echo "ERROR: Invalid cron schedule format: '$schedule'"
        echo "ERROR: Cron schedule must have 5 fields (minute hour day month weekday)"
        echo "ERROR: Example of valid schedule: '0 2 * * *' (runs at 2:00 AM daily)"
        return 1
    fi
    
    return 0
}

# Print banner
echo "====================================================="
echo "TrueNAS Auto Update"
echo "$(date)"
echo "====================================================="

# Check which scheduling method to use
if [ -n "$CRON_SCHEDULE" ]; then
    echo "Validating cron schedule: $CRON_SCHEDULE"
    
    if ! validate_cron_schedule "$CRON_SCHEDULE"; then
        echo "Exiting due to invalid cron schedule"
        exit 1
    fi
    
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
    env | grep -v "no_proxy" > /etc/environment
    
    # Start cron service and tail the log
    service cron start
    echo "Cron job installed with schedule: $CRON_SCHEDULE"
    echo "Watching logs..."
    tail -f /var/log/cron.log
    
elif [ -n "$INTERVAL_SECONDS" ]; then
    echo "Running in interval mode every $INTERVAL_SECONDS seconds"
    
    while true; do
        echo "Starting update check at $(date)"
        python app.py
        echo "Finished update check, sleeping for $INTERVAL_SECONDS seconds"
        sleep $INTERVAL_SECONDS
    done
    
else
    echo "Running once (no scheduling configured)"
    exec python app.py
fi