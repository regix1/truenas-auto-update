#!/bin/bash
set -e

# Function to validate cron schedule with better checking
validate_cron_schedule() {
    local schedule="$1"
    
    # Basic validation - make sure there are 5 fields with spaces between them
    if ! [[ "$schedule" =~ ^[0-9*/-]+(\ [0-9*/-]+){4}$ ]]; then
        echo "ERROR: Invalid cron schedule format: '$schedule'"
        echo "ERROR: Cron schedule must have 5 fields separated by spaces (minute hour day month weekday)"
        echo "ERROR: Example of valid schedule: '0 5 * * *' (runs at 5:00 AM daily)"
        return 1
    fi
    
    return 0
}

# Function to get TrueNAS version info
get_truenas_info() {
    if [ -z "$BASE_URL" ] || [ -z "$API_KEY" ]; then
        echo "WARNING: BASE_URL or API_KEY not set, cannot retrieve TrueNAS info"
        return 1
    fi
    
    echo "Connecting to TrueNAS at $BASE_URL..."
    
    # Try to get system info using REST API
    response=$(curl -s -k -H "Authorization: Bearer $API_KEY" "$BASE_URL/api/v2.0/system/info" || echo '{"error": "Connection failed"}')
    
    # Check if response contains version info
    if echo "$response" | grep -q "version"; then
        version=$(echo "$response" | grep -o '"version":[^,}]*' | cut -d'"' -f4)
        hostname=$(echo "$response" | grep -o '"hostname":[^,}]*' | cut -d'"' -f4)
        echo "TrueNAS Info:"
        echo "  Hostname: $hostname"
        echo "  Version:  $version"
        echo "  API:      REST"
    elif echo "$response" | grep -q "error"; then
        echo "ERROR: Could not connect to TrueNAS API"
        echo "Response: $response"
    else
        echo "WARNING: Unknown response format"
    fi
}

# Print banner
echo "====================================================="
echo "TrueNAS Auto Update"
echo "$(date)"
echo "====================================================="

# Get TrueNAS info at startup
get_truenas_info

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
    
    # Handle locale settings properly (fix for the deprecation warning)
    mkdir -p /etc/default
    echo "LANG=C.UTF-8" > /etc/default/locale
    
    # Export other environment variables for cron jobs
    mkdir -p /app/env
    env | grep -v "LANG=" | grep -v "LC_" | grep -v "no_proxy" > /app/env/cron-env
    
    # Modify the cron job to source environment variables
    sed -i "s|cd /app && python|cd /app \&\& . /app/env/cron-env \&\& python|" /etc/cron.d/app-cron
    
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