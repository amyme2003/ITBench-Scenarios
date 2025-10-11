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


def enable_alert(alert_id):
    """Enable a specific alert."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs/{alert_id}/enable"
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
def enable_alerts():
    print("🔔 Enabling disabled alerts...")
    alerts = get_alerts()
    disabled_alerts = [a for a in alerts if a.get("id") and not a.get("enabled")]

    if not disabled_alerts:
        print("No disabled alerts found.")
        return

    for alert in disabled_alerts:
        alert_id = alert["id"]
        print(f"Enabling alert ID: {alert_id}")
        enable_alert(alert_id)
        details = get_alert_details(alert_id)
        print_alert_details(details)

    print("All disabled alerts have been enabled.")


if __name__ == "__main__":
    try:
        enable_alerts()
    except requests.exceptions.RequestException as e:
        print(f"Error enabling alerts: {e}")
        sys.exit(1)
