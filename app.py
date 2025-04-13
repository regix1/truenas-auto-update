import logging
import os
import time
import json
import re
import sys

import apprise
import requests
import websocket

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
APPRISE_URLS = os.getenv("APPRISE_URLS", "").strip()
NOTIFY_ON_SUCCESS = os.getenv("NOTIFY_ON_SUCCESS", "false").lower() == "true"
FORCE_WEBSOCKET = os.getenv("FORCE_WEBSOCKET", "false").lower() == "true"

# Initialize Apprise for notifications if configured
apobj = apprise.Apprise()
if APPRISE_URLS:
    for url in APPRISE_URLS.split(","):
        apobj.add(url.strip())

def send_notification(title, message):
    """Send a notification if Apprise URLs have been provided."""
    if APPRISE_URLS:
        apobj.notify(title=title, body=message)
        logger.info(f"Notification sent: {title}")

if not BASE_URL or not API_KEY:
    logger.error("BASE_URL or API_KEY is not set")
    send_notification("Configuration Error", "BASE_URL or API_KEY is not set")
    sys.exit(1)

# Determine if we should use WebSocket API or REST API
def detect_truenas_version():
    """Detect TrueNAS version to determine which API to use."""
    try:
        # Try to access the REST API endpoint for system info
        rest_url = f"{BASE_URL.rstrip('/')}/api/v2.0/system/info"
        response = requests.get(
            rest_url,
            headers={"Authorization": f"Bearer {API_KEY}"},
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            version_info = response.json()
            version = version_info.get("version", "")
            # Extract version number (e.g., 24.04, 25.04)
            match = re.search(r'(\d+\.\d+)', version)
            if match:
                version_num = float(match.group(1))
                logger.info(f"Detected TrueNAS version: {version}")
                # If version is 25.04 or higher, use WebSocket API
                if version_num >= 25.04 or FORCE_WEBSOCKET:
                    return "websocket"
        return "rest"
    except Exception as e:
        logger.warning(f"Failed to detect TrueNAS version: {str(e)}")
        logger.info("Falling back to REST API")
        return "rest"

# WebSocket API implementation
class TrueNASWebSocketAPI:
    def __init__(self, base_url, api_key):
        # Convert the base URL to WebSocket URL
        ws_url = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/websocket"
        self.api_key = api_key
        self.ws = None
        self.call_id = 1
        
    def connect(self):
        try:
            self.ws = websocket.create_connection(
                self.ws_url,
                header={"Authorization": f"Bearer {self.api_key}"}
            )
            logger.info("Connected to TrueNAS WebSocket API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {str(e)}")
            return False
    
    def disconnect(self):
        if self.ws:
            self.ws.close()
            logger.info("Disconnected from TrueNAS WebSocket API")
    
    def call(self, method, params=None):
        if not self.ws:
            if not self.connect():
                return None
        
        call_id = self.call_id
        self.call_id += 1
        
        request = {
            "id": call_id,
            "msg": "method",
            "method": method,
            "params": params or []
        }
        
        try:
            self.ws.send(json.dumps(request))
            response = json.loads(self.ws.recv())
            
            if response.get("id") != call_id:
                logger.error("Received response with mismatched ID")
                return None
            
            if "error" in response:
                logger.error(f"API error: {response['error']}")
                return None
            
            return response.get("result")
        except Exception as e:
            logger.error(f"WebSocket call failed: {str(e)}")
            return None
    
    def get_chart_releases(self):
        return self.call("chart.release.query")
    
    def upgrade_chart_release(self, release_name):
        return self.call("chart.release.upgrade", [release_name])
    
    def wait_for_job(self, job_id):
        return self.call("core.job_wait", [job_id])

# REST API implementation
class TrueNASRestAPI:
    def __init__(self, base_url, api_key):
        # Normalize the base URL to ensure no trailing slash, and add the API path
        self.base_url = base_url.rstrip("/") + "/api/v2.0"
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def get_chart_releases(self):
        try:
            response = requests.get(
                f"{self.base_url}/chart/release",
                headers=self.headers,
                verify=False,
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get chart releases: {response.status_code}")
                return None
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get chart releases: {str(e)}")
            return None
    
    def upgrade_chart_release(self, release_name):
        try:
            upgrade_response = requests.post(
                f"{self.base_url}/chart/release/upgrade",
                headers=self.headers,
                json={"release_name": release_name},
                verify=False,
            )
            
            if upgrade_response.status_code != 200:
                logger.error(f"Failed to trigger upgrade: {upgrade_response.status_code}")
                return None
            
            # Assuming the API returns the job id as plain text
            return upgrade_response.text.strip()
        except Exception as e:
            logger.error(f"Exception while upgrading: {str(e)}")
            return None
    
    def wait_for_job(self, job_id):
        try:
            job_response = requests.post(
                f"{self.base_url}/core/job_wait",
                headers=self.headers,
                json=job_id,
                verify=False,
            )
            
            if job_response.status_code != 200:
                logger.error(f"Job {job_id} did not complete successfully: {job_response.status_code}")
                return None
            
            return job_response
        except Exception as e:
            logger.error(f"Failed to wait for job {job_id}: {str(e)}")
            return None

def update_charts():
    """Main function to update all available chart releases"""
    logger.info("Starting chart update check")
    
    # Determine which API to use
    api_type = detect_truenas_version()
    logger.info(f"Using API type: {api_type}")
    
    # Create the appropriate API client
    if api_type == "websocket":
        api_client = TrueNASWebSocketAPI(BASE_URL, API_KEY)
    else:
        api_client = TrueNASRestAPI(BASE_URL, API_KEY)
    
    # Step 1: Retrieve installed chart releases
    releases = api_client.get_chart_releases()
    
    if not releases:
        error_msg = f"Failed to get chart releases on {BASE_URL}"
        logger.error(error_msg)
        send_notification("Error", error_msg)
        if api_type == "websocket":
            api_client.disconnect()
        return False
    
    # Step 2: Filter releases that need an update
    def needs_update(release):
        return release.get("update_available") or release.get("container_images_update_available")
    
    releases_to_upgrade = [r for r in releases if needs_update(r)]
    logger.info(f"Found {len(releases_to_upgrade)} chart release(s) that need an update")
    
    update_count = 0
    
    # Step 3: Loop over each release and trigger an upgrade
    for release in releases_to_upgrade:
        # Try to use the release_name from the top-level, then from config, then fall back to the "id"
        release_identifier = (
            release.get("release_name")
            or release.get("config", {}).get("release_name")
            or release.get("id")
        )
        if not release_identifier:
            logger.warning("Found a release without a valid identifier; skipping.")
            continue
        
        logger.info(f"Upgrading chart release {release_identifier}...")
        
        job_id = api_client.upgrade_chart_release(release_identifier)
        
        if not job_id:
            error_msg = f"Failed to trigger upgrade for {release_identifier}"
            logger.error(error_msg)
            send_notification("Upgrade Failed", error_msg)
            continue
        
        job_result = api_client.wait_for_job(job_id)
        
        if job_result:
            success_msg = f"Upgrade for {release_identifier} triggered successfully"
            logger.info(success_msg)
            update_count += 1
            if NOTIFY_ON_SUCCESS:
                send_notification("Chart Updated", f"Successfully updated {release_identifier}")
        else:
            error_msg = f"Upgrade job for {release_identifier} failed or did not complete successfully."
            logger.error(error_msg)
            send_notification("Upgrade Failed", error_msg)
        
        time.sleep(1)
    
    if api_type == "websocket":
        api_client.disconnect()
    
    logger.info(f"Completed with {update_count} successful updates out of {len(releases_to_upgrade)} attempts")
    return update_count > 0

if __name__ == "__main__":
    update_charts()