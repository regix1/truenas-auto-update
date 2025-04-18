import logging
import os
import time
import json
import re
import sys
import urllib3
import platform
from datetime import datetime

import apprise
import requests
import websocket

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Print startup banner
def print_banner():
    logger.info("=" * 60)
    logger.info(f"TrueNAS Auto Update starting")
    logger.info(f"Python version: {platform.python_version()}")
    logger.info(f"System: {platform.system()} {platform.release()}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

print_banner()

# Environment variables
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
APPRISE_URLS = os.getenv("APPRISE_URLS", "").strip()
NOTIFY_ON_SUCCESS = os.getenv("NOTIFY_ON_SUCCESS", "false").lower() == "true"
FORCE_WEBSOCKET = os.getenv("FORCE_WEBSOCKET", "false").lower() == "true"
TZ = os.getenv("TZ", "UTC")

logger.info(f"Configuration:")
logger.info(f"  BASE_URL: {BASE_URL}")
logger.info(f"  API_KEY: {'Configured' if API_KEY else 'Not configured'}")
logger.info(f"  NOTIFY_ON_SUCCESS: {NOTIFY_ON_SUCCESS}")
logger.info(f"  FORCE_WEBSOCKET: {FORCE_WEBSOCKET}")
logger.info(f"  TZ: {TZ}")
logger.info(f"  APPRISE_URLS: {'Configured' if APPRISE_URLS else 'Not configured'}")

# Initialize Apprise for notifications if configured
apobj = apprise.Apprise()
if APPRISE_URLS:
    for url in APPRISE_URLS.split(","):
        apobj.add(url.strip())
        logger.info(f"Added notification URL: {url.strip()[:10]}...")

def send_notification(title, message):
    """Send a notification if Apprise URLs have been provided."""
    if APPRISE_URLS:
        try:
            apobj.notify(title=title, body=message)
            logger.info(f"Notification sent: {title}")
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")

if not BASE_URL or not API_KEY:
    error_msg = "BASE_URL or API_KEY is not set"
    logger.error(error_msg)
    send_notification("Configuration Error", error_msg)
    sys.exit(1)

# Determine if we should use WebSocket API or REST API
def detect_truenas_version():
    """Detect TrueNAS version to determine which API to use."""
    logger.info(f"Detecting TrueNAS version at {BASE_URL}...")
    
    try:
        # Try to access the REST API endpoint for system info
        rest_url = f"{BASE_URL.rstrip('/')}/api/v2.0/system/info"
        logger.info(f"Checking REST API endpoint: {rest_url}")
        
        response = requests.get(
            rest_url,
            headers={"Authorization": f"Bearer {API_KEY}"},
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            version_info = response.json()
            version = version_info.get("version", "")
            hostname = version_info.get("hostname", "unknown")
            system_serial = version_info.get("system_serial", "unknown")
            
            logger.info(f"Connected to TrueNAS system:")
            logger.info(f"  Hostname: {hostname}")
            logger.info(f"  Version: {version}")
            logger.info(f"  System Serial: {system_serial}")
            
            # Extract version number (e.g., 24.04, 25.04)
            match = re.search(r'(\d+\.\d+)', version)
            if match:
                version_num = float(match.group(1))
                logger.info(f"Detected TrueNAS version number: {version_num}")
                
                # If version is 25.04 or higher, use WebSocket API
                if version_num >= 25.04 or FORCE_WEBSOCKET:
                    logger.info(f"Using WebSocket API (TrueNAS 25.04+ detected or forced)")
                    return "websocket", version
                else:
                    logger.info(f"Using REST API (TrueNAS pre-25.04 detected)")
                    return "rest", version
            else:
                logger.warning(f"Could not parse version number from: {version}")
                return "rest", version
        else:
            logger.error(f"Failed to get system info: HTTP {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            return "rest", "unknown"
            
    except Exception as e:
        logger.warning(f"Failed to detect TrueNAS version: {str(e)}")
        logger.info("Falling back to REST API")
        return "rest", "unknown"

# WebSocket API implementation - updated for TrueNAS 25.04+
class TrueNASWebSocketAPI:
    def __init__(self, base_url, api_key):
        ws_url = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/websocket"
        self.api_key = api_key
        self.ws = None
        self.call_id = 1
        self.connected = False
        self.session_id = None
        logger.info(f"Initializing WebSocket API client at {self.ws_url}")
        
    def connect(self):
        try:
            logger.info(f"Connecting to WebSocket API...")
            # Set a reasonable timeout for the connection (10 seconds)
            self.ws = websocket.create_connection(
                self.ws_url,
                header={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            
            # Send the initial connect message per DDP protocol
            connect_request = {
                "msg": "connect",
                "version": "1",
                "support": ["1"]
            }
            logger.debug(f"Sending connect message: {connect_request}")
            self.ws.send(json.dumps(connect_request))
            
            # Wait for connected response with timeout
            self.ws.settimeout(5)
            connect_response = json.loads(self.ws.recv())
            logger.debug(f"Received response: {connect_response}")
            
            if connect_response.get("msg") == "connected":
                self.session_id = connect_response.get("session")
                self.connected = True
                logger.info(f"Connected to TrueNAS WebSocket API successfully (Session: {self.session_id})")
                return True
            else:
                logger.error(f"Failed to connect: {connect_response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {str(e)}")
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
                self.ws = None
            return False
    
    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")
            finally:
                self.ws = None
                self.connected = False
                self.session_id = None
                logger.info("Disconnected from TrueNAS WebSocket API")
    
    def call(self, method, params=None):
        if not self.connected:
            if not self.connect():
                return None
        
        call_id = self.call_id
        self.call_id += 1
        
        request = {
            "id": str(call_id),  # Convert to string to match DDP protocol
            "msg": "method",
            "method": method,
            "params": params or []
        }
        
        try:
            logger.debug(f"Sending method call: {method} (ID: {call_id})")
            self.ws.send(json.dumps(request))
            
            # Set reasonable timeout for response
            self.ws.settimeout(30)
            
            while True:
                try:
                    response = json.loads(self.ws.recv())
                    logger.debug(f"Received response: {response}")
                    
                    # Check if this is our response
                    if response.get("id") == str(call_id) and response.get("msg") == "result":
                        if "error" in response:
                            logger.error(f"API error: {response['error']}")
                            return None
                        
                        return response.get("result")
                    
                    # If not our response, log and continue waiting
                    logger.debug(f"Received message with ID {response.get('id')}, expecting {call_id}")
                    
                except websocket.WebSocketTimeoutException:
                    logger.error(f"Timeout waiting for response to method call: {method}")
                    return None
                
        except Exception as e:
            logger.error(f"WebSocket call failed: {str(e)}")
            self.connected = False
            return None

# REST API implementation
class TrueNASRestAPI:
    def __init__(self, base_url, api_key):
        # Normalize the base URL to ensure no trailing slash, and add the API path
        self.base_url = base_url.rstrip("/") + "/api/v2.0"
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}
        logger.info(f"Initializing REST API client at {self.base_url}")
    
    def get_chart_releases(self):
        try:
            logger.info("Fetching chart releases via REST API...")
            response = requests.get(
                f"{self.base_url}/chart/release",
                headers=self.headers,
                verify=False,
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get chart releases: HTTP {response.status_code}")
                return None
            
            releases = response.json()
            logger.info(f"Retrieved {len(releases)} chart releases")
            return releases
        except Exception as e:
            logger.error(f"Failed to get chart releases: {str(e)}")
            return None
    
    def upgrade_chart_release(self, release_name):
        try:
            logger.info(f"Triggering upgrade for {release_name} via REST API...")
            upgrade_response = requests.post(
                f"{self.base_url}/chart/release/upgrade",
                headers=self.headers,
                json={"release_name": release_name},
                verify=False,
            )
            
            if upgrade_response.status_code != 200:
                logger.error(f"Failed to trigger upgrade: HTTP {upgrade_response.status_code}")
                return None
            
            # Assuming the API returns the job id as plain text
            job_id = upgrade_response.text.strip()
            logger.info(f"Upgrade job created: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Exception while upgrading: {str(e)}")
            return None
    
    def wait_for_job(self, job_id):
        try:
            logger.info(f"Waiting for job {job_id} to complete...")
            job_response = requests.post(
                f"{self.base_url}/core/job_wait",
                headers=self.headers,
                json=job_id,
                verify=False,
            )
            
            if job_response.status_code != 200:
                logger.error(f"Job {job_id} did not complete successfully: HTTP {job_response.status_code}")
                return None
            
            logger.info(f"Job {job_id} completed successfully")
            return job_response
        except Exception as e:
            logger.error(f"Failed to wait for job {job_id}: {str(e)}")
            return None

def update_charts():
    """Main function to update all available chart releases"""
    logger.info("Starting chart update check")
    
    # Determine which API to use
    api_type, version = detect_truenas_version()
    logger.info(f"Using API type: {api_type} for TrueNAS version: {version}")
    
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
    
    if not releases_to_upgrade:
        logger.info("No chart releases need updates at this time")
    else:
        logger.info(f"Found {len(releases_to_upgrade)} chart release(s) that need an update:")
        for r in releases_to_upgrade:
            name = r.get("release_name") or r.get("config", {}).get("release_name") or r.get("id")
            logger.info(f"  - {name}")
    
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
    
    summary_msg = f"Completed with {update_count} successful updates out of {len(releases_to_upgrade)} attempts"
    logger.info(summary_msg)
    logger.info("=" * 60)
    return update_count > 0

if __name__ == "__main__":
    update_charts()