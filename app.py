import logging
import os
import time
import json
import re
import sys
import urllib3
import platform
from datetime import datetime

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
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
USE_SSL = os.getenv("USE_SSL", "false").lower() == "true"
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"
NOTIFY_ON_SUCCESS = os.getenv("NOTIFY_ON_SUCCESS", "false").lower() == "true"
TZ = os.getenv("TZ", "UTC")

logger.info(f"Configuration:")
logger.info(f"  BASE_URL: {BASE_URL}")
logger.info(f"  API_KEY: {'Configured' if API_KEY else 'Not configured'}")
logger.info(f"  USERNAME: {'Configured' if USERNAME else 'Not configured'}")
logger.info(f"  USE_SSL: {USE_SSL}")
logger.info(f"  VERIFY_SSL: {VERIFY_SSL}")
logger.info(f"  NOTIFY_ON_SUCCESS: {NOTIFY_ON_SUCCESS}")
logger.info(f"  TZ: {TZ}")

if not BASE_URL:
    logger.error("BASE_URL is required")
    sys.exit(1)

if not (API_KEY or (USERNAME and PASSWORD)):
    logger.error("Either API_KEY or both USERNAME and PASSWORD must be provided")
    sys.exit(1)

# Determine if we should use WebSocket API or REST API
def is_new_api():
    url = f"{'https' if USE_SSL else 'http'}://{BASE_URL}/api/versions"
    try:
        response = requests.get(url, verify=VERIFY_SSL)
        return response.status_code == 200
    except:
        return False

# WebSocket authentication
def websocket_auth(ws):
    if USERNAME and PASSWORD:
        ws.send(json.dumps({"id": "auth", "msg": "method", "method": "auth.login", "params": [USERNAME, PASSWORD]}))
    elif API_KEY:
        ws.send(json.dumps({"id": "auth", "msg": "method", "method": "auth.login_with_api_key", "params": [API_KEY]}))
    else:
        raise Exception("No authentication credentials provided.")
    
    result = json.loads(ws.recv())
    if result.get("result") != True:
        raise Exception("Authentication failed")

# WebSocket API class
class TrueNASWebSocketAPI:
    def __init__(self):
        self.ws = None
        self.call_id = 1
        self.connect()
        
    def connect(self):
        try:
            ws_url = f"{'wss' if USE_SSL else 'ws'}://{BASE_URL}/websocket"
            logger.info(f"Connecting to WebSocket API at {ws_url}")
            
            self.ws = websocket.create_connection(
                ws_url, 
                sslopt={"cert_reqs": 0} if not VERIFY_SSL else {}
            )
            
            # Initial connection message
            self.ws.send(json.dumps({"msg": "connect", "version": "1"}))
            if json.loads(self.ws.recv()).get("msg") != "connected":
                raise Exception("WebSocket connection failed")
                
            # Authenticate
            websocket_auth(self.ws)
            logger.info("Successfully authenticated with WebSocket API")
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket API: {str(e)}")
            if self.ws:
                self.ws.close()
                self.ws = None
            raise
    
    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {str(e)}")
            finally:
                self.ws = None
    
    def call(self, method, params=None):
        if not self.ws:
            self.connect()
            
        call_id = str(self.call_id)
        self.call_id += 1
        
        request = {
            "id": call_id,
            "msg": "method",
            "method": method,
            "params": params or []
        }
        
        try:
            logger.debug(f"Sending WebSocket call: {method}")
            self.ws.send(json.dumps(request))
            response = json.loads(self.ws.recv())
            
            if response.get("id") != call_id:
                logger.error(f"Received response with mismatched ID: {response.get('id')} vs {call_id}")
                return None
                
            if "error" in response:
                logger.error(f"API error: {response.get('error')}")
                return None
                
            return response.get("result")
            
        except Exception as e:
            logger.error(f"WebSocket call failed: {str(e)}")
            self.disconnect()
            return None
    
    def get_chart_releases(self):
        logger.info("Fetching apps via WebSocket API...")
        releases = self.call("app.query")
        if releases:
            logger.info(f"Retrieved {len(releases)} apps")
        else:
            logger.error("Failed to retrieve apps")
        return releases
    
    def upgrade_chart_release(self, release_name):
        logger.info(f"Triggering upgrade for {release_name} via WebSocket API...")
        return self.call("app.upgrade", [release_name])
    
    def wait_for_job(self, job_id):
        logger.info(f"Waiting for job {job_id} to complete...")
        return self.call("core.job_wait", [job_id])

# REST API class
class TrueNASRestAPI:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
        self.base_url = f"{'https' if USE_SSL else 'http'}://{BASE_URL}/api/v2.0"
        
    def get_chart_releases(self):
        try:
            logger.info("Fetching chart releases via REST API...")
            response = requests.get(
                f"{self.base_url}/chart/release",
                headers=self.headers,
                verify=VERIFY_SSL,
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
                verify=VERIFY_SSL,
            )
            
            if upgrade_response.status_code != 200:
                logger.error(f"Failed to trigger upgrade: HTTP {upgrade_response.status_code}")
                return None
            
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
                verify=VERIFY_SSL,
            )
            
            if job_response.status_code != 200:
                logger.error(f"Job {job_id} did not complete successfully: HTTP {job_response.status_code}")
                return None
            
            logger.info(f"Job {job_id} completed successfully")
            return job_response.json()
            
        except Exception as e:
            logger.error(f"Failed to wait for job {job_id}: {str(e)}")
            return None

def update_charts():
    """Main function to update all available chart releases"""
    logger.info("Starting chart update check")
    
    # Determine which API to use
    new_api = is_new_api()
    logger.info(f"Using {'new WebSocket' if new_api else 'old REST'} API")
    
    # Create the appropriate API client
    if new_api:
        api_client = TrueNASWebSocketAPI()
    else:
        api_client = TrueNASRestAPI()
    
    try:
        # Step 1: Retrieve installed chart releases
        releases = api_client.get_chart_releases()
        
        if not releases:
            logger.error(f"Failed to get chart releases")
            return False
        
        # Step 2: Filter releases that need an update
        def needs_update(release):
            # Check for various update indicators across different TrueNAS versions
            return (
                release.get("update_available", False) or 
                release.get("container_images_update_available", False) or
                release.get("update_available_train", False) or
                release.get("outdated", False) or
                release.get("needs_update", False)
            )
        
        releases_to_upgrade = [r for r in releases if needs_update(r)]
        
        if not releases_to_upgrade:
            logger.info("No chart releases need updates at this time")
            return True
        
        logger.info(f"Found {len(releases_to_upgrade)} chart release(s) that need an update:")
        for r in releases_to_upgrade:
            # Try to find the name using various field names across different TrueNAS versions
            name = (
                r.get("name") or 
                r.get("release_name") or 
                r.get("id") or
                r.get("app_name") or
                "unknown"
            )
            logger.info(f"  - {name}")
        
        update_count = 0
        
        # Step 3: Loop over each release and trigger an upgrade
        for release in releases_to_upgrade:
            # Get the release identifier based on the API version
            release_identifier = (
                release.get("name") or
                release.get("release_name") or
                release.get("config", {}).get("release_name") or
                release.get("id") or
                release.get("app_name")
            )
            if not release_identifier:
                logger.warning("Found a release without a valid identifier; skipping.")
                continue
            
            logger.info(f"Upgrading release {release_identifier}...")
            
            job_id = api_client.upgrade_chart_release(release_identifier)
            
            if not job_id:
                logger.error(f"Failed to trigger upgrade for {release_identifier}")
                continue
            
            job_result = api_client.wait_for_job(job_id)
            
            if job_result:
                success_msg = f"Upgrade for {release_identifier} completed successfully"
                logger.info(success_msg)
                update_count += 1
            else:
                logger.error(f"Upgrade job for {release_identifier} failed")
            
            time.sleep(1)
        
        summary_msg = f"Completed with {update_count} successful updates out of {len(releases_to_upgrade)} attempts"
        logger.info(summary_msg)
        return update_count > 0
        
    finally:
        # Clean up resources
        if new_api and hasattr(api_client, 'disconnect'):
            api_client.disconnect()

if __name__ == "__main__":
    try:
        update_charts()
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        sys.exit(1)