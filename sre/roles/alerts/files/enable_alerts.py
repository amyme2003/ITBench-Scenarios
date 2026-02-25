#!/usr/bin/env python3
import requests
import os
import sys
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -------------------------------
# Configuration from environment
# -------------------------------
BASE_URL = os.getenv("BASE_URL")
APPLICATION_ID = os.getenv("APPLICATION_ID")
TOKEN = os.getenv("TOKEN")
INCIDENT_ID = os.getenv("INCIDENT_ID")

if not BASE_URL or not APPLICATION_ID or not TOKEN:
    print("Missing required environment variables: BASE_URL, APPLICATION_ID, or TOKEN")
    sys.exit(1)

HEADERS = {"Authorization": f"apiToken {TOKEN}"}
INCIDENT_PREFIX_PATTERN = re.compile(r'^ITBench Incident \d+:\s*')

# -------------------------------
# Core functions
# -------------------------------
def get_alerts():
    """Fetch all alerts for a given application."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs?applicationId={APPLICATION_ID}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_alert_details(alert_id):
    """Fetch details of a specific alert by ID."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs/{alert_id}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def update_alert_config(alert_id, config):
    """Update alert configuration."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs/{alert_id}"
    # Add Content-Type header for JSON payload
    headers = {**HEADERS, "Content-Type": "application/json"}
    resp = requests.post(url, json=config, headers=headers)
    resp.raise_for_status()
    return resp.json()


def enable_alert(alert_id):
    """Enable a specific alert."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs/{alert_id}/enable"
    resp = requests.put(url, headers=HEADERS)
    resp.raise_for_status()


def should_update_alert_name(alert_name):
    """Check if alert name has an ITBench Incident prefix that should be updated."""
    if not INCIDENT_ID:
        return False
    
    # Check if the alert name starts with "ITBench Incident <number>:"
    return bool(INCIDENT_PREFIX_PATTERN.match(alert_name))


def get_new_alert_name(alert_name, incident_id):
    """
    Generate new alert name by replacing the incident number.
    Preserves everything after the incident prefix.
    """
    # Remove the old "ITBench Incident <number>:" prefix
    base_name = INCIDENT_PREFIX_PATTERN.sub('', alert_name)
    
    # Add the new incident prefix
    return f"ITBench Incident {incident_id}: {base_name}"


def print_alert_details(alert):
    """Pretty-print alert details."""
    print("→ Alert Details:")
    print(f"   Name: {alert.get('name')}")
    print(f"   ID: {alert.get('id')}")
    print(f"   Enabled: {alert.get('enabled')}")
    print("-----------------------------------")


# -------------------------------
# Main logic
# -------------------------------
def enable_alerts():
    """Enable disabled alerts and update their names with incident ID."""
    if INCIDENT_ID:
        print(f"Enabling disabled alerts and updating names with Incident ID: {INCIDENT_ID}...")
    else:
        print("Enabling disabled alerts (no INCIDENT_ID provided, names will not be updated)...")
    
    alerts = get_alerts()
    disabled_alerts = [a for a in alerts if a.get("id") and not a.get("enabled")]

    if not disabled_alerts:
        print("No disabled alerts found.")
        return

    enabled_count = 0
    updated_name_count = 0

    for alert in disabled_alerts:
        alert_id = alert["id"]
        alert_name = alert.get("name", "")
        
        print(f"\nProcessing alert ID: {alert_id}")
        print(f"Current name: {alert_name}")
        
        # Update name if INCIDENT_ID is provided and alert matches pattern
        if INCIDENT_ID and should_update_alert_name(alert_name):
            # Get full alert configuration
            alert_config = get_alert_details(alert_id)
            
            # Generate new name with incident ID
            new_name = get_new_alert_name(alert_name, INCIDENT_ID)
            
            if new_name:
                # Update the name field
                alert_config['name'] = new_name
                print(f"Updating name to: {new_name}")
                
                # Update the configuration (this will also preserve the disabled state)
                update_alert_config(alert_id, alert_config)
                updated_name_count += 1
        
        # Enable the alert
        print(f"Enabling alert ID: {alert_id}")
        enable_alert(alert_id)
        enabled_count += 1
        
        # Get and display final details
        details = get_alert_details(alert_id)
        print_alert_details(details)

    print(f"\nSuccessfully enabled {enabled_count} alert(s)")
    if INCIDENT_ID and updated_name_count > 0:
        print(f"Successfully updated {updated_name_count} alert name(s) with Incident ID: {INCIDENT_ID}")


if __name__ == "__main__":
    try:
        enable_alerts()
    except requests.exceptions.RequestException as e:
        print(f"Error enabling alerts: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
