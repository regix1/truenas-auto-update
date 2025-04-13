FROM python:3.12-slim

# Install cron, curl and locales
RUN apt-get update && \
    apt-get install -y cron curl locales && \
    rm -rf /var/lib/apt/lists/* && \
    localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

# Set locale
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY docker-entrypoint.sh .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Create log file for cron
RUN touch /var/log/cron.log

# Set the entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]