#!/usr/bin/env python3
import os
import sys
import time
import requests
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
ALERTS_ENABLED_AT_MS = int(os.getenv("ALERTS_ENABLED_AT_MS", 0) or 0)

if not BASE_URL or not TOKEN:
    print("Missing required environment variables: BASE_URL or TOKEN")
    sys.exit(1)

if not APPLICATION_ID:
    print("Missing required environment variable: APPLICATION_ID")
    sys.exit(1)

if not INCIDENT_ID:
    print("Missing required environment variable: INCIDENT_ID")
    sys.exit(1)

HEADERS = {"Authorization": f"apiToken {TOKEN}"}

WINDOW_SIZE_MS = 900000  # 15 minutes fallback


# -------------------------------
# Core functions
# -------------------------------
def get_alert_configs():
    """Fetch all application alert configs to collect event specification IDs."""
    url = f"{BASE_URL}/api/events/settings/application-alert-configs?applicationId={APPLICATION_ID}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def query_incidents(spec_id, now_ms, window_size_ms=WINDOW_SIZE_MS):
    """Query incidents for a single event specification ID within the given time window."""
    query = f"event.specification.id:{spec_id} AND event.type:incident AND event.rca.found:true"
    url = (
        f"{BASE_URL}/api/events/events-query"
        f"?query={requests.utils.quote(query)}"
        f"&windowSize={window_size_ms}"
        f"&to={now_ms}"
        f"&orderBy=start"
    )
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    # API may return a list directly or a dict with an 'items' / 'data' key
    if isinstance(data, list):
        return data
    return data.get("items", data.get("data", []))


def filter_by_scenario(events, incident_id):
    """Keep only events whose problem field contains the scenario incident_id."""
    matched = []
    for event in events:
        problem = event.get("problem", "") or ""
        if str(incident_id) in problem:
            matched.append(event)
    return matched


def trigger_investigation(event_id):
    """POST to the Instana automated investigation trigger endpoint. Returns True on success."""
    url = f"{BASE_URL}/api/automated-investigation/trigger/{event_id}"
    resp = requests.post(url, headers=HEADERS)
    if resp.ok:
        return True
    print(f"WARNING: Failed to trigger investigation for event {event_id} — "
          f"HTTP {resp.status_code}: {resp.text}")
    return False


# -------------------------------
# Main logic
# -------------------------------
def main():
    now_ms = int(time.time() * 1000)

    if ALERTS_ENABLED_AT_MS:
        window_size_ms = now_ms - ALERTS_ENABLED_AT_MS
        print(f"Using dynamic window: alerts_enabled_at={ALERTS_ENABLED_AT_MS}ms, now={now_ms}ms, window={window_size_ms}ms ({window_size_ms // 1000}s)")
    else:
        window_size_ms = WINDOW_SIZE_MS
        print(f"ALERTS_ENABLED_AT_MS not set — using fallback window of {WINDOW_SIZE_MS}ms (15 min)")

    print(f"Fetching alert configs for application_id: {APPLICATION_ID} ...")
    configs = get_alert_configs()
    spec_ids = [c["id"] for c in configs if c.get("id")]
    print(f"Found {len(spec_ids)} alert config(s) with spec IDs.")

    all_events = []
    for spec_id in spec_ids:
        print(f"Querying incidents for spec_id: {spec_id} ...")
        events = query_incidents(spec_id, now_ms, window_size_ms)
        print(f"  → {len(events)} incident(s) returned.")
        all_events.extend(events)
        for event in events:
            print(event.get("eventId"))

    print(f"\nTotal incidents collected across all spec IDs: {len(all_events)}")

    matched = filter_by_scenario(all_events, INCIDENT_ID)
    print(f"Incidents matching scenario '{INCIDENT_ID}': {len(matched)}")

    if not matched:
        print("No matching incidents found. Nothing to trigger.")
        sys.exit(0)

    failed = 0
    for event in matched:
        event_id = event.get("eventId")
        if not event_id:
            print(f"WARNING: Skipping event with no id — {event}")
            failed += 1
            continue
        problem = event.get("problem", "")
        print(f"Triggering investigation for event '{event_id}' (problem: {problem}) ...")
        if not trigger_investigation(event_id):
            failed += 1
        time.sleep(3)

    print(f"\nSummary: {len(matched) - failed} triggered successfully, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Instana API: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
