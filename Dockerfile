FROM python:3.12-slim

# Install required packages including cron and gettext-base for envsubst (if needed)
RUN apt-get update && \
    apt-get install -y cron gettext-base && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the application code (main.py, etc.)
COPY app/ .

# Copy the condensed entrypoint script and make it executable
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create log file for cron (if needed)
RUN touch /var/log/cron.log

# Set the entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
