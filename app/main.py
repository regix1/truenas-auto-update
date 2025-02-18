import logging
import os
import time

import apprise
import requests

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
APPRISE_URLS = os.getenv("APPRISE_URLS", "").strip()
NOTIFY_ON_SUCCESS = os.getenv("NOTIFY_ON_SUCCESS", "false").lower() == "true"

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
    exit(1)

# Normalize the base URL to ensure no trailing slash, and add the API path
BASE_URL = BASE_URL.rstrip("/") + "/api/v2.0"

# --- Step 1: Retrieve installed chart releases ---
try:
    response = requests.get(
        f"{BASE_URL}/chart/release",
        headers={"Authorization": f"Bearer {API_KEY}"},
        verify=False,
    )
except Exception as e:
    logger.error(f"Failed to get chart releases: {str(e)}")
    send_notification("Error", f"Failed to get chart releases on {BASE_URL}: {str(e)}")
    exit(1)

if response.status_code != 200:
    logger.error(f"Failed to get chart releases: {response.status_code}")
    send_notification("Error", f"Failed to get chart releases on {BASE_URL}: {response.status_code}")
    exit(1)

releases = response.json()

# --- Step 2: Filter releases that need an update ---
def needs_update(release):
    return release.get("update_available") or release.get("container_images_update_available")

releases_to_upgrade = [r for r in releases if needs_update(r)]
logger.info(f"Found {len(releases_to_upgrade)} chart release(s) that need an update")

# --- Helper: Wait for an asynchronous job to complete ---
def await_job(job_id):
    logger.info(f"Waiting for job {job_id} to complete...")
    try:
        job_response = requests.post(
            f"{BASE_URL}/core/job_wait",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=job_id,
            verify=False,
        )
    except Exception as e:
        logger.error(f"Failed to wait for job {job_id}: {str(e)}")
        return None

    if job_response.status_code != 200:
        logger.error(f"Job {job_id} did not complete successfully: {job_response.status_code}")
        return None

    return job_response

# --- Step 3: Loop over each release and trigger an upgrade ---
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

    try:
        # Use the corrected endpoint for upgrades
        upgrade_response = requests.post(
            f"{BASE_URL}/chart/release/upgrade",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"release_name": release_identifier},
            verify=False,
        )
    except Exception as e:
        error_msg = f"Exception while upgrading {release_identifier}: {str(e)}"
        logger.error(error_msg)
        send_notification("Upgrade Failed", error_msg)
        continue

    if upgrade_response.status_code != 200:
        error_msg = f"Failed to trigger upgrade for {release_identifier}: {upgrade_response.status_code}"
        logger.error(error_msg)
        send_notification("Upgrade Failed", error_msg)
        continue

    # Assuming the API returns the job id as plain text
    job_id = upgrade_response.text.strip()
    job_result = await_job(job_id)

    if job_result and job_result.status_code == 200:
        success_msg = f"Upgrade for {release_identifier} triggered successfully"
        logger.info(success_msg)
        if NOTIFY_ON_SUCCESS:
            send_notification("Chart Updated", f"Successfully updated {release_identifier}")
    else:
        error_msg = f"Upgrade job for {release_identifier} failed or did not complete successfully."
        logger.error(error_msg)
        send_notification("Upgrade Failed", error_msg)

    time.sleep(1)

logger.info("Done")
