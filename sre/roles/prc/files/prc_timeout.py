"""
PRC Enrichment with Timeout - Type ENDPOINT, SERVICE, or INFRASTRUCTURE

This is a modified version of the PRC script with a timeout to prevent long-running operations.
"""

import asyncio
import json
import logging
import os
import sys
import signal
from typing import Any, Dict, List, Tuple, Set
from dotenv import load_dotenv

import httpx

# === Constants and Configuration ===

# Load environment variables from .env file
load_dotenv()

# API URLs
BASE_URL = "https://release-instana.instana.rocks"
INCIDENTS_API_URL = f"{BASE_URL}/api/events?eventTypeFilters=INCIDENT"

# Get API token from environment variable
API_TOKEN = os.environ.get("INSTANA_API_TOKEN")
if not API_TOKEN:
    print("INSTANA_API_TOKEN environment variable is not set.")
    sys.exit(1)
    
HEADERS = {
    "Authorization": f"apiToken {API_TOKEN}",
    "Content-Type": "application/json"
}

# Output configuration
OUTPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "prc_label_new.json")

# === Logger Setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# === Incident Fetcher ===

async def fetch_incidents_data() -> List[Dict[str, Any]]:
    """Fetch incident data from the Instana API with a timeout."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(INCIDENTS_API_URL, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, list):
                print("Expected a list of incidents")
                return []
                
            return data
    except httpx.HTTPStatusError as e:
        print(f"HTTP error {e.response.status_code}: {e}")
        return []
    except httpx.RequestError as e:
        print(f"Request error: {e}")
        return []
    except Exception as e:
        print(f"Failed to fetch incidents: {e}")
        return []

def filter_prc_incidents(incidents_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter incidents to only include those with probable root causes."""
    return [
        incident for incident in incidents_data
        if incident.get("type") == "incident"
        and incident.get("state") == "open"
        and incident.get("probableCause", {}).get("found") is True
    ]

def save_output_to_file(output: Dict[str, Any], file_path: str) -> None:
    """Save the output data to a JSON file."""
    try:
        with open(file_path, "w") as f:
            json.dump(output, f, indent=4)
        print(f"Output saved to {file_path}")
    except Exception as e:
        print(f"Failed to save output: {e}")

async def process_incident(incident: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Process an incident to create the enriched entry."""
    trigger_id = incident.get("eventId", "")
    trigger_label = incident.get("entityLabel", "Unknown")
    prc = incident.get("probableCause", {})
    
    # Create the enriched entry
    entry = {
        "entityType": incident.get("entityType", ""),
        "problem": incident.get("problem", ""),
        "detail": incident.get("detail", ""),
        "probableCause": prc
    }

    key = f"Triggering Event ID: {trigger_id} | Triggering Entity Label: {trigger_label}"
    return key, entry

async def main():
    """Main function to fetch and process incidents."""
    print("Fetching incidents from Instana...")
    incidents_data = await fetch_incidents_data()
    print(f"Fetched {len(incidents_data)} incidents")
    
    prc_incidents = filter_prc_incidents(incidents_data)
    print(f"Found {len(prc_incidents)} PRC incidents")
    
    # Process all incidents concurrently
    results = await asyncio.gather(
        *[process_incident(incident) for incident in prc_incidents]
    )
    
    # Build output dictionary
    output = {}
    for key, entry in results:
        output[key] = entry
    
    save_output_to_file(output, OUTPUT_FILE_PATH)
    return output

if __name__ == "__main__":
    # Set a timeout handler
    def timeout_handler(signum, frame):
        print("Execution timed out after 120 seconds")
        sys.exit(1)
    
    # Set a 2-minute timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(120)
    
    try:
        asyncio.run(main())
        print("PRC data fetched successfully")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Cancel the timeout
        signal.alarm(0)

# Made with Bob
