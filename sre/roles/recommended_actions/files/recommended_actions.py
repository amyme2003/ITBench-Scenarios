#!/usr/bin/env python3
"""
 Recommended Actions

Run the file and put /trigger in the path to get the output
This service fetches incident data with probable root causes (PRC) and triggers recommended actions by sending the incident details to the Recommended AI action
generation endpoint. All responses are included regardless of confidence level, and each response is enumerated with an index.
The results are saved to a JSON file.
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
import os
import sys
import httpx
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
import os
from pathlib import Path

# Get the absolute path to the .env file
base_dir = Path(__file__).resolve().parent
env_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path=env_path)

# === Logger Setup ===
logger = logging.getLogger("remediation_trigger")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Configuration from environment
BASE_URL = os.getenv("BASE_URL")
APPLICATION_ID = os.getenv("APPLICATION_ID")
API_TOKEN = os.getenv("TOKEN")

# Validate required environment variables
if not BASE_URL or not API_TOKEN:
    print("Missing required environment variables: BASE_URL or TOKEN")
    sys.exit(1)

# Log the configuration
logger.info(f"Using Instana base URL: {BASE_URL}")
if APPLICATION_ID:
    logger.info(f"Using application ID: {APPLICATION_ID}")

# API URLs
INCIDENTS_API_URL = f"{BASE_URL}/api/events?eventTypeFilters=INCIDENT"
REC_ACTION_GENERATION_URL = f"{BASE_URL}/api/automation/ai/action/match"

HEADERS = {
    "Authorization": f"apiToken {API_TOKEN}",
    "Content-Type": "application/json"
}

# Get incident ID from environment variable (passed from AWX UI extra variables)
INCIDENT_ID = os.environ.get("INCIDENT_ID")
if INCIDENT_ID and INCIDENT_ID.isdigit():
    incident_id = int(INCIDENT_ID)
    logger.info(f"Using incident_id {incident_id} from environment variable")
elif INCIDENT_ID:
    logger.warning(f"Invalid incident_id format: {INCIDENT_ID}. Must be a number.")
    incident_id = None
else:
    incident_id = None  # No default, will show all incidents if not specified
    logger.info(f"No incident_id provided, will show all matching incidents")

# Output configuration
OUTPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "Rec_all.json")

# === FastAPI App ===
app = FastAPI(
    title="Recommended actions API",
    description="API for fetching recommended actions",
    version="1.0.0"
)

# === Pydantic Models ===
class RemediationResponse(BaseModel):
    total_incidents: int
    prc_incidents: int
    processed_incidents: int
    results: List[Dict[str, Any]]

# === API Calls ===

async def fetch_incidents() -> List[Dict[str, Any]]:
    """Fetch incidents from API."""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(INCIDENTS_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            raise ValueError("Expected a list of incidents")

        logger.info(f"Fetched {len(data)} incidents")
        return data


def filter_prc_incidents(incidents_data: List[Dict[str, Any]], incident_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Filter incidents to only include those with probable root causes.
    Different filtering criteria are applied based on the incident_id.
    
    Args:
        incidents_data: The full list of incidents
        incident_id: Optional incident ID to filter by
        
    Returns:
        A filtered list containing only PRC incidents
    """
    # Log information about the incidents before filtering
    states = set(incident.get("state") for incident in incidents_data)
    types = set(incident.get("type") for incident in incidents_data)
    prc_counts = sum(1 for incident in incidents_data if incident.get("probableCause", {}).get("found") is True)
    
    logger.info(f"Incident states found: {states}")
    logger.info(f"Incident types found: {types}")
    logger.info(f"Incidents with PRC found=True: {prc_counts}")
    logger.info(f"Filtering for incident_id: {incident_id if incident_id is not None else 'All'}")
    
    # Apply different filtering criteria based on incident_id
    if incident_id == 23:
        # Filtering criteria for incident_id 23
        filtered = [
            incident for incident in incidents_data
            if incident.get("type") == "incident"
            and incident.get("probableCause", {}).get("found") is True
            and incident.get("entityLabel", "").startswith(("otel-demo-frontend","otel-demo-checkout","frontend","checkout"))   
            and incident.get("problem","").startswith("Alert on all services")
        ]
    elif incident_id == 3:
        # Filtering criteria for incident_id 3
        filtered = [
            incident for incident in incidents_data
            if incident.get("type") == "incident"
            and incident.get("probableCause", {}).get("found") is True
            and incident.get("entityLabel", "").startswith(("otel-demo-frontend","frontend"))
            and incident.get("problem","").startswith("Alert on all services")
        ]
    else:
        filtered = [
            incident for incident in incidents_data
            if incident.get("type") == "incident"
            and incident.get("probableCause", {}).get("found") is True
            and incident.get("problem","").startswith("Alert on all services")
        ]
    
    logger.info(f"After filtering: {len(filtered)} PRC incidents")
    
    # Check if no incidents were found after filtering
    if len(filtered) == 0:
        logger.info("No incidents found after filtering.")
        print("No incidents found after filtering.")
    
    return filtered


async def trigger_remediation(incident: Dict[str, Any], incident_id) -> Dict[str, Any]:
    """Trigger recommended actions API for one incident."""
    event_id = incident.get("eventId")
    entity_label = incident.get("entityLabel")
    
    # Fetch event specification info
    event_spec_id = incident.get("eventSpecificationId")
    event_spec_info = ""
    event_entity_type = incident.get("eventEntityType")
    
    if event_spec_id:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                spec_response = await client.get(f"{BASE_URL}/api/events/settings/application-alert-configs/{event_spec_id}",
                    headers=HEADERS,
                   
                )
                spec_response.raise_for_status()
                
                response_data = spec_response.json()
                event_spec_info = response_data.get("description", "") if response_data else ""
                #event_entity_type = response_data[0].get("entityType", "") if response_data else ""
                
                # Format entity type with proper capitalization (Infrastructure instead of INFRASTRUCTURE)
                if event_entity_type:
                    event_entity_type = event_entity_type.capitalize()
                logger.info(f"Fetched event specification info for {event_id}")
        except Exception as e:
            logger.error(f"Error fetching event specification info for {event_id}: {str(e)}")
    
    # Create post body with updated structure
    post_body = {
        "name": incident.get("problem"),
        "description": event_spec_info,
        "type": "default",
        "eventId": event_id
    }

    try:
        # First API call with original payload - with retry logic
        max_retries = 3
        retry_delay = 2  # seconds
        response = None
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        REC_ACTION_GENERATION_URL,
                        headers=HEADERS,
                        json=post_body
                    )
                    response.raise_for_status()
                    logger.info(f"Success for first API call: {event_id}")
                    break  # Success, exit retry loop
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 500 and attempt < max_retries - 1:
                    # Server error, retry after delay
                    logger.warning(f"Server error (500) for {event_id}, retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Either not a 500 error or we've exhausted retries
                    raise
        
        if response is None:
            raise ValueError("Failed to get a valid response after retries")
            
        # Get the response data
        response_data = response.json() if response.text else {}
        
        # Process all responses without filtering by confidence
        if isinstance(response_data, list):
            # Enumerate the responses
            enumerated_response = []
            for i, item in enumerate(response_data, 1):
                enumerated_item = {"index": i}
                enumerated_item.update(item)
                enumerated_response.append(enumerated_item)
            
            total_entries = len(enumerated_response)
            first_response = {
                "request_body": post_body,
                "incident_id": incident_id,
                "entityLabel": entity_label,
                "response": enumerated_response,
                "total_entries": total_entries
            }
        else:
            first_response = {
                "request_body": post_body,
                "incident_id": incident_id,
                "entityLabel": entity_label,
                "response": response_data,
                "total_entries": 1 if response_data else 0
            }
        
        # Process probable causes and make additional API calls
        probable_cause = incident.get("probableCause", {})
        current_root_causes = probable_cause.get("currentRootCause", [])
        
        # Return the filtered response
        return first_response
    except httpx.HTTPStatusError as e:
        # HTTPStatusError has response attribute
        logger.error(f"HTTP status error for {event_id}: {repr(e)}, Status: {e.response.status_code}")
        return {
            "request_body": post_body,
            "entityLabel": entity_label,
            "incident_id": incident_id,
            "error": str(e),
            "error_status": e.response.status_code,
            "total_entries": 0
        }
    except httpx.RequestError as e:
        # Network-related errors
        logger.error(f"Request error for {event_id}: {repr(e)}")
        return {
            "request_body": post_body,
            "entityLabel": entity_label,
            "incident_id": incident_id,
            "error": str(e),
            "error_type": "network_error",
            "total_entries": 0
        }
    except Exception as e:
        # Any other unexpected errors
        logger.error(f"Unexpected error for {event_id}: {repr(e)}")
        return {
            "request_body": post_body,
            "entityLabel": entity_label,
            "incident_id": incident_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "total_entries": 0
        }


def save_results(results: List[Dict[str, Any]]) -> None:
    """Save results to JSON file."""
    with open(OUTPUT_FILE_PATH, "w") as f:
        json.dump(results, f, indent=4)
    logger.info(f"Results saved to {OUTPUT_FILE_PATH}")


# === Main Runner ===

async def main():
    incidents = await fetch_incidents()
    prc_incidents = filter_prc_incidents(incidents, incident_id)

    results = []
    for inc in prc_incidents:
        res = await trigger_remediation(inc, incident_id)
        results.append(res)

    save_results(results)
    return results


# === API Endpoints ===
@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "name": "Recommended Actions Trigger API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "This information"},
            {"path": "/trigger", "method": "GET", "description": "Trigger recommended actions for all PRC incidents"},
            {"path": "/health", "method": "GET", "description": "Health check endpoint"}
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/trigger", response_model=RemediationResponse)
async def trigger_remediation_endpoint(background_tasks: BackgroundTasks):
    """
    Trigger remediation for all PRC incidents.
    
    This endpoint fetches all incidents with probable root causes and
    triggers automated remediation actions for each one.
    """
    try:
        # Run the main function
        results = await main()
        
        # Count incidents
        incidents_count = len(results) if results else 0
        
        return RemediationResponse(
            total_incidents=incidents_count,
            prc_incidents=incidents_count,
            processed_incidents=incidents_count,
            results=results
        )
    except Exception as e:
        logger.error(f"Error in trigger endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# Function to process data and exit
async def process_data_and_exit():
    """Process the data and exit without starting the web server"""
    try:
        # Fetch and process incidents
        incidents = await fetch_incidents()
        prc_incidents = filter_prc_incidents(incidents, incident_id)

        results = []
        for inc in prc_incidents:
            res = await trigger_remediation(inc, incident_id)
            results.append(res)

        save_results(results)
        
        # Print output for AWX to capture
        output_data = {
            "results": results,
            "status": "success" if results else "no_incidents_found"
        }
        print(json.dumps(output_data))
        
        logger.info("Data processing completed successfully")
        
    except Exception as e:
        logger.exception(f"Error processing data: {e}")
        # Print error for AWX to capture
        error_data = {
            "status": "error",
            "message": str(e)
        }
        print(json.dumps(error_data))
        raise


if __name__ == "__main__":
    # When run in AWX environment or with API token, just process the data and exit
    asyncio.run(process_data_and_exit())


