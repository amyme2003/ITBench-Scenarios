#!/usr/bin/env python3
"""
Remediation for Triggering Context and PRC

This service fetches incident data with probable root causes (PRC) and triggers
manual AI generated actions by sending the incident details to the AI action
generation endpoint. The first response is for the triggering entity, actions for PRC 
are added under the heading additional responses.
The results are saved to a JSON file.
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
import os
import httpx
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
import os
from pathlib import Path

# Load environment variables
load_dotenv()

# === Logger Setup ===
logger = logging.getLogger("remediation_trigger")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# API URLs
BASE_URL = "https://release-instana.instana.rocks"
INCIDENTS_API_URL = f"{BASE_URL}/api/events?eventTypeFilters=INCIDENT"
ACTION_GENERATION_URL = f"{BASE_URL}/api/automation/ai/action/generate"

# Get API token from environment variable
API_TOKEN = os.environ.get("INSTANA_API_TOKEN")
if not API_TOKEN:
    raise ValueError("INSTANA_API_TOKEN environment variable is not set. Please set it in the .env file.")
HEADERS = {
    "Authorization": f"apiToken {API_TOKEN}",
    "Content-Type": "application/json"
}
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


def filter_prc_incidents(incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only open PRC incidents."""
    seen_ids = set()
    prc_incidents = []
    for inc in incidents:
        if (
            inc.get("type") == "incident"
            and inc.get("state") == "open"
            and inc.get("probableCause", {}).get("found") is True
        ):
            eid = inc.get("eventId")
            if eid not in seen_ids:
                seen_ids.add(eid)
                prc_incidents.append(inc)

    logger.info(f"Filtered to {len(prc_incidents)} PRC incidents")
    return prc_incidents


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

    # Fetch event specification info
    event_spec_id = incident.get("eventSpecificationId")
    event_spec_info = ""
    event_entity_type = ""

    if event_spec_id:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                spec_response = await client.post(
                    f"{BASE_URL}/api/events/settings/event-specifications/infos",
                    headers=HEADERS,
                    json=[event_spec_id]
                )
                spec_response.raise_for_status()

                response_data = spec_response.json()
                event_spec_info = response_data[0].get("description", "") if response_data else ""
                event_entity_type = response_data[0].get("entityType", "") if response_data else ""

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

    try:
        # First API call with original payload
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                ACTION_GENERATION_URL,
                headers=HEADERS,
                json=post_body
            )
            response.raise_for_status()
            logger.info(f"Success for first API call: {event_id}")

            first_response = {
                "incident_id": event_id,
                "entity_label": entity_label,
                "status_code": response.status_code,
                "request_body": post_body,
                "response": response.json() if response.text else {}
            }

        # Process probable causes and make additional API calls
        probable_cause = incident.get("probableCause", {})
        current_root_causes = probable_cause.get("currentRootCause", [])

        additional_responses = []

        for root_cause in current_root_causes:
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

        # Combine all responses
        return {
            **first_response,
            "additional_responses": additional_responses
        }

    except httpx.HTTPError as e:
        logger.error(f"HTTP error for {event_id}: {repr(e)}")
        return {
            "incident_id": event_id,
            "entity_label": entity_label,
            "status_code": 0,
            "request_body": post_body,
            "error": str(e)
        }


def save_results(results: List[Dict[str, Any]]) -> None:
    """Save results to JSON file."""
    with open(OUTPUT_FILE_PATH, "w") as f:
        json.dump(results, f, indent=4)
    logger.info(f"Results saved to {OUTPUT_FILE_PATH}")


# === Main Runner ===

async def main():
    incidents = await fetch_incidents()
    prc_incidents = filter_prc_incidents(incidents)

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


if __name__ == "__main__":
    import uvicorn

    # Configure uvicorn server
    uvicorn.run(
        "remediation_trigger:app", 
        host="127.0.0.1", 
        port=8007, 
        reload=True,
        log_level="info"
    )


