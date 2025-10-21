#!/usr/bin/env python3
"""
 WIP- Remediation for Triggering Context and PRC

Run the file and put /trigger in the path to get the output
This service fetches incident data with probable root causes (PRC) and triggers
manual ai generated actions by sending the incident details to the AI action
generation endpoint.The first response is for the triggering entity , actions for prc are added under the heading additional responses.
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
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
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
ACTION_GENERATION_URL = f"{BASE_URL}/api/automation/ai/action/generate"

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
OUTPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "remediation_output.json")

# === FastAPI App ===
app = FastAPI(
    title="Remediation Trigger API",
    description="API for fetching incidents and triggering automated remediation actions",
    version="1.0.0"
)

# === Pydantic Models ===
class RemediationResponse(BaseModel):
    results: List[Dict[str, Any]]

# === API Calls ===

async def fetch_incidents() -> List[Dict[str, Any]]:
    """Fetch incidents from API."""
    # Calculate time parameters for the last 24 hours
    #to_timestamp = int(time.time() * 1000)  # Current time in milliseconds
    #window_size = 3600000    # last 1 hours in milliseconds
    
    # Build URL with time parameters
    #url = f"{INCIDENTS_API_URL}&to={to_timestamp}&windowSize={window_size}"
    #Modified_url=f"{BASE_URL}/api/events?eventTypeFilters=INCIDENT&from=1758575400000&to=1758748199000"
    #logger.info(f"Fetching incidents with a 18sep to 19sep window (to={to_timestamp}, windowSize={window_size})")
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
            and incident.get("entityLabel", "").startswith(("otel-demo-frontend","frontend","checkout","otel-demo-checkout"))
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


async def get_endpoint_label(steady_id: str, timestamp: int) -> str:
    """Fetch endpoint label for a given endpoint ID."""
    if not steady_id:
        return "Unknown Endpoint"
        
    try:
        endpoint_url = f"{BASE_URL}/api/application-monitoring/metrics/endpoints"
        payload = {
            "endpointId": steady_id,
            "metrics": [{"aggregation": "MEAN", "metric": "latency"}],
            "timeFrame": {
                "to": timestamp,
                "windowSize": 3600000  # 1 hour in milliseconds
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint_url, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if items and "endpoint" in items[0]:
                endpoint_data = items[0]["endpoint"]
                return endpoint_data.get("label", "Unknown Endpoint")

            logger.warning(f"No valid endpoint data found for steadyId {steady_id}")
            return "Unknown Endpoint"

    except Exception as e:
        logger.error(f"Error fetching endpoint label for {steady_id}: {str(e)}")
        return "Unknown Endpoint"

async def get_service_label(service_id: str, timestamp: int) -> str:
    """Fetch service label for a given service ID."""
    if not service_id:
        return "Unknown Service"
        
    try:
        service_url = f"{BASE_URL}/api/application-monitoring/metrics/services"
        payload = {
            "serviceId": service_id,
            "metrics": [{"aggregation": "MEAN", "metric": "latency"}],
            "timeFrame": {
                "to": timestamp,
                "windowSize": 3600000  # 1 hour in milliseconds
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(service_url, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if items and "service" in items[0] and "label" in items[0]["service"]:
                return items[0]["service"]["label"]
                
            logger.warning(f"No service label found for service_id={service_id}")
            return "Unknown Service"
            
    except Exception as e:
        logger.error(f"Error fetching service label for {service_id}: {str(e)}")
        return "Unknown Service"

async def get_infrastructure_label(snapshot_id: str, plugin_id: str, timestamp: int) -> str:
    """Fetch infrastructure label for a given snapshot ID."""
    if not snapshot_id:
        return "Unknown Infrastructure"
        
    try:
        # Determine the tag filter name based on the plugin_id
        tag_filter_name = "id.host"  # Default
        
        if plugin_id:
            if "host" in plugin_id.lower():
                tag_filter_name = "id.host"
            elif "process" in plugin_id.lower():
                tag_filter_name = "id.process"
            elif "opentelemetry" in plugin_id.lower():
                tag_filter_name = "id.otel"
        
        infrastructure_url = f"{BASE_URL}/api/infrastructure-monitoring/analyze/entities"
        payload = {
            "tagFilterExpression": {
                "type": "TAG_FILTER",
                "name": tag_filter_name,
                "operator": "EQUALS",
                "entity": "NOT_APPLICABLE",
                "value": snapshot_id
            },
            "timeFrame": {
                "to": timestamp,
                "windowSize": 3600000  # 1 hour in milliseconds
            },
            "pagination": {
                "retrievalSize": 200
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(infrastructure_url, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if items:
                # Find the item with matching snapshot ID
                for item in items:
                    if item.get("snapshotId") == snapshot_id:
                        return item.get("label", "Unknown Infrastructure")
                
                # If no exact match found, return the first item's label
                return items[0].get("label", "Unknown Infrastructure")
            
            logger.warning(f"No infrastructure details found for snapshot_id={snapshot_id}")
            return "Unknown Infrastructure"
            
    except Exception as e:
        logger.error(f"Error fetching infrastructure label for {snapshot_id}: {str(e)}")
        return "Unknown Infrastructure"

def get_plugin_type(plugin_id: str) -> str:
    """Determine the plugin type from the plugin ID."""
    if not plugin_id:
        return "unknown"
        
    if "endpoint" in plugin_id.lower():
        return "endpoint"
    elif "service" in plugin_id.lower():
        return "service"
    elif "infrastructure" in plugin_id.lower():
        return "infrastructure"
    else:
        return "unknown"

async def trigger_remediation(incident: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger remediation API for one incident."""
    event_id = incident.get("eventId")
    entity_label = incident.get("entityLabel")
    event_entity_type = incident.get("entityType")
    # Fetch event specification info
    event_spec_id = incident.get("eventSpecificationId")
    event_spec_info = ""
    
    
    if event_spec_id:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                spec_response = await client.get(
                    f"{BASE_URL}/api/events/settings/application-alert-configs/{event_spec_id}",
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
        "eventId": event_id,
        "eventEntityType": event_entity_type,
        "eventName": incident.get("problem"),
        "eventDescription": f"Event {incident.get('problem')} with description {event_spec_info}"
    }

    # Initialize first_response and additional_responses
    first_response = {
        "incident_id": incident_id,
        "event_id": event_id,
        "entity_label": entity_label,
        "request_body": post_body
    }
    additional_responses = []
    
    # Make first API call
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                ACTION_GENERATION_URL,
                headers=HEADERS,
                json=post_body
            )
            response.raise_for_status()
            logger.info(f"Success for first API call: {event_id}")
            
            first_response.update({
                "status_code": response.status_code,
                "response": response.json() if response.text else {}
            })
    except httpx.HTTPError as e:
        logger.error(f"HTTP error for first API call {event_id}: {repr(e)}")
        first_response.update({
            "status_code": 0,
            "error": str(e)
        })
    
    # Process probable causes and make additional API calls regardless of first call's success
    probable_cause = incident.get("probableCause", {})
    current_root_causes = probable_cause.get("currentRootCause", [])
    
    # Process each root cause
    for root_cause in current_root_causes:
        try:
            entity_id = root_cause.get("entityID", {})
            plugin_id = entity_id.get("pluginId", "")
            
            # Get timestamp from the root cause or use current time as fallback
            timestamp = root_cause.get("timestamp", int(time.time() * 1000))
            
            # Determine plugin type
            plugin_type = get_plugin_type(plugin_id)
            
            # Get label based on plugin type
            label = "Unknown"
            entity_id_value = ""
            
            if plugin_type == "endpoint":
                steady_id = entity_id.get("steadyId", "")
                label = await get_endpoint_label(steady_id, timestamp)
                entity_id_value = steady_id
            elif plugin_type == "service":
                steady_id = entity_id.get("steadyId", "")
                label = await get_service_label(steady_id, timestamp)
                entity_id_value = steady_id
            elif plugin_type == "infrastructure":
                # For infrastructure plugins, use snapshotId instead of steadyId
                snapshot_id = None
                for item in root_cause.get("explainability", []):
                    if "relevantSnapshotID" in item:
                        snapshot_id = item.get("relevantSnapshotID")
                        break
                        
                if not snapshot_id:
                    # If not found in explainability, check if it's directly in the cause
                    snapshot_id = root_cause.get("snapshotId")
                    
                if snapshot_id:
                    label = await get_infrastructure_label(snapshot_id, plugin_id, timestamp)
                    entity_id_value = snapshot_id
            
            # Create payload for additional API call
            entity_type = plugin_type.capitalize()
            diagnosis_context = plugin_type
            
            # Special case for infrastructure plugin with process in pluginID
            if plugin_type == "infrastructure" and plugin_id and "process" in plugin_id.lower():
                entity_type = "Process"
                diagnosis_context = "process"
                
            additional_payload = {
                "eventId": event_id,
                "eventDiagnosis": f"Higher than expected error rate going through {label} in {diagnosis_context}",
                "eventEntityType": entity_type
            }
            
            # Make additional API call
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    additional_response = await client.post(
                        ACTION_GENERATION_URL,
                        headers=HEADERS,
                        json=additional_payload
                    )
                    additional_response.raise_for_status()
                    logger.info(f"Success for additional API call for {plugin_type} {entity_id_value}")
                    
                    additional_responses.append({
                        "plugin_type": plugin_type,
                        "entity_id": entity_id_value,
                        "label": label,
                        "status_code": additional_response.status_code,
                        "request_body": additional_payload,
                        "response": additional_response.json() if additional_response.text else {}
                    })
            except httpx.HTTPError as e:
                logger.error(f"HTTP error for additional API call for {plugin_type} {entity_id_value}: {repr(e)}")
                additional_responses.append({
                    "plugin_type": plugin_type,
                    "entity_id": entity_id_value,
                    "label": label,
                    "status_code": 0,
                    "request_body": additional_payload,
                    "error": str(e)
                })
        except Exception as e:
            # Catch any other exceptions that might occur during processing a root cause
            logger.error(f"Error processing root cause: {str(e)}")
            additional_responses.append({
                "error": f"Failed to process root cause: {str(e)}"
            })
    
    # Combine all responses
    return {
        **first_response,
        "additional_responses": additional_responses
    }


def save_results(results: List[Dict[str, Any]]) -> None:
    """Save results to JSON file."""
    # Create output data structure for AWX artifacts
    output_data = {
        "results": results,
        "status": "success" if results else "no_incidents_found"
    }
    
    # Save to file
    with open(OUTPUT_FILE_PATH, "w") as f:
        json.dump(output_data, f, indent=4)
    logger.info(f"Results saved to {OUTPUT_FILE_PATH}")
    
    # Also print summary to stdout for AWX logs
    print(f"Processed {len(results)} incidents with probable root causes")
    if results:
        print(f"Results saved to {OUTPUT_FILE_PATH}")
    else:
        print("No matching incidents found")


# === Main Runner ===
async def main():
    incidents = await fetch_incidents()
    prc_incidents = filter_prc_incidents(incidents, incident_id)

    results = []
    for inc in prc_incidents:
        res = await trigger_remediation(inc)
        results.append(res)

    save_results(results)
    return results


# === API Endpoints ===
@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "name": "Remediation Trigger API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "This information"},
            {"path": "/trigger", "method": "GET", "description": "Trigger remediation for all PRC incidents"},
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
            res = await trigger_remediation(inc)
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

# === Main Entry Point ===
if __name__ == "__main__":
    # Check if running in AWX environment
    if os.environ.get("AWX_EXECUTION") or os.environ.get("TOKEN"):
        # When run in AWX, just process the data and exit
        asyncio.run(process_data_and_exit())
    else:
        # When run as a standalone service, start the FastAPI server
        import uvicorn
        
        # Configure uvicorn server
        uvicorn.run(
            "remediation_trigger:app",
            host="127.0.0.1",
            port=8017,
            reload=True,
            log_level="info"
        )


