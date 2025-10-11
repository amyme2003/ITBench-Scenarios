#!/usr/bin/env python3
import requests
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# -------------------------------
# Configuration from environment
# -------------------------------
BASE_URL = os.getenv("BASE_URL")
APPLICATION_ID = os.getenv("APPLICATION_ID")
TOKEN = os.getenv("TOKEN")

if not BASE_URL or not APPLICATION_ID or not TOKEN:
    print("Missing required environment variables: BASE_URL, APPLICATION_ID, or TOKEN")
    sys.exit(1)

HEADERS = {"Authorization": f"apiToken {TOKEN}"}


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


def disable_alert(alert_id):
    """Disable a specific alert."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs/{alert_id}/disable"
    resp = requests.put(url, headers=HEADERS)
    resp.raise_for_status()


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
def disable_alerts():
    print("Disabling enabled alerts...")
    alerts = get_alerts()
    enabled_alerts = [a for a in alerts if a.get("id") and a.get("enabled")]

    if not enabled_alerts:
        print("No enabled alerts found.")
        return

    for alert in enabled_alerts:
        alert_id = alert["id"]
        print(f"Disabling alert ID: {alert_id}")
        disable_alert(alert_id)
        details = get_alert_details(alert_id)
        print_alert_details(details)

    print("All enabled alerts have been disabled.")


if __name__ == "__main__":
    try:
        disable_alerts()
    except requests.exceptions.RequestException as e:
        print(f"Error disabling alerts: {e}")
        sys.exit(1)
