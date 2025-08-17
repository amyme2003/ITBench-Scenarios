"""
PRC Enrichment - pluginId- Type ENDPOINT or SERVICE

This service fetches incident data with probable root causes (PRC) and enriches it
with endpoint and service labels.
Please note taking into account only pluginId of type Endpoint and Service
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dotenv import load_dotenv

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# === Constants and Configuration ===

# Load environment variables from .env file
load_dotenv()

# API URLs
BASE_URL = "https://release-instana.instana.rocks"
INCIDENTS_API_URL = f"{BASE_URL}/api/events?eventTypeFilters=INCIDENT"
ENDPOINT_METRICS_URL = f"{BASE_URL}/api/application-monitoring/metrics/endpoints"
SERVICE_METRICS_URL = f"{BASE_URL}/api/application-monitoring/metrics/services"

# Get API token from environment variable
API_TOKEN = os.environ.get("INSTANA_API_TOKEN")
if not API_TOKEN:
    raise ValueError("INSTANA_API_TOKEN environment variable is not set. Please set it in the .env file.")
HEADERS = {
    "Authorization": f"apiToken {API_TOKEN}",
    "Content-Type": "application/json"
}

# Output configuration
# Save to current working directory
OUTPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "prc_label.json")

# Time window for metrics queries (1 hour in milliseconds)
METRICS_WINDOW_SIZE = 3600000

# === Logger Setup ===
logger = logging.getLogger("prc_enrich")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# === FastAPI App ===
app = FastAPI(
    title="PRC Enrichment API",
    description="API for fetching and enriching Probable Root Cause data",
    version="9.0.0"
)

# === Metric Fetchers ===

async def get_service_label(service_id: str, to_timestamp: int) -> str:
    """
    Fetch service label for a given service ID.
    
    Args:
        service_id: The ID of the service to fetch the label for
        to_timestamp: The timestamp to fetch metrics at
        
    Returns:
        The service label or a default value if not found
    """
    if not service_id:
        return "Unknown Service"
        
    try:
        payload = {
            "serviceId": service_id,
            "metrics": [{"aggregation": "MEAN", "metric": "latency"}],
            "timeFrame": {
                "to": to_timestamp,
                "windowSize": METRICS_WINDOW_SIZE
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(SERVICE_METRICS_URL, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if items and "service" in items[0] and "label" in items[0]["service"]:
                return items[0]["service"]["label"]
                
            logger.warning(f"No service label found for service_id={service_id}")
            return "Unknown Service"
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching service label for {service_id}: {e.response.status_code}")
        return "Unknown Service"
    except httpx.RequestError as e:
        logger.error(f"Request error fetching service label for {service_id}: {e}")
        return "Unknown Service"
    except Exception as e:
        logger.error(f"Error fetching service label for {service_id}: {e}")
        return "Unknown Service"


async def get_endpoint_label(steady_id: str, to_timestamp: int) -> Tuple[str, str, str]:
    """
    Fetch endpoint label and associated service information for a given endpoint ID.
    
    Args:
        steady_id: The steady ID of the endpoint
        to_timestamp: The timestamp to fetch metrics at
        
    Returns:
        A tuple containing (endpoint_label, service_id, service_label)
    """
    if not steady_id:
        return "Unknown Endpoint", "", "Unknown Service"
        
    try:
        payload = {
            "endpointId": steady_id,
            "metrics": [{"aggregation": "MEAN", "metric": "latency"}],
            "timeFrame": {
                "to": to_timestamp,
                "windowSize": METRICS_WINDOW_SIZE
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(ENDPOINT_METRICS_URL, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if items and "endpoint" in items[0]:
                endpoint_data = items[0]["endpoint"]
                endpoint_label = endpoint_data.get("label", "Unknown Endpoint")
                service_id = endpoint_data.get("serviceId", "")

                service_label = await get_service_label(service_id, to_timestamp) if service_id else "Unknown Service"
                return endpoint_label, service_id, service_label

            logger.warning(f"No valid endpoint data found for steadyId {steady_id}")
            return "Unknown Endpoint", "", "Unknown Service"

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching endpoint label for {steady_id}: {e.response.status_code}")
        return f"Error Endpoint ({steady_id})", "", "Unknown Service"
    except httpx.RequestError as e:
        logger.error(f"Request error fetching endpoint label for {steady_id}: {e}")
        return f"Error Endpoint ({steady_id})", "", "Unknown Service"
    except Exception as e:
        logger.exception(f"Exception while fetching endpoint label for {steady_id}: {e}")
        return f"Error Endpoint ({steady_id})", "", "Unknown Service"


# === Incident Helpers ===

async def fetch_incidents_data() -> List[Dict[str, Any]]:
    """
    Fetch incident data from the Instana API.
    
    Returns:
        A list of incident data dictionaries
        
    Raises:
        ValueError: If the response is not a list
        httpx.HTTPError: If there's an HTTP error
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(INCIDENTS_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, list):
            raise ValueError("Expected a list of incidents")
            
        return data


def filter_prc_incidents(incidents_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter incidents to only include those with probable root causes.
    
    Args:
        incidents_data: The full list of incidents
        
    Returns:
        A filtered list containing only PRC incidents
    """
    return [
        incident for incident in incidents_data
        if incident.get("type") == "incident"
        and incident.get("state") == "open"
        and incident.get("probableCause", {}).get("found") is True
    ]


# === Plugin Handler Registry ===

# Define a type for plugin handler functions
PluginHandler = Any

# Registry to map plugin types to their handler functions
PLUGIN_HANDLERS: Dict[str, PluginHandler] = {
    "Endpoint": get_endpoint_label,
    "Service": get_service_label
    
}

# Result processor functions for different plugin types
def process_endpoint_result(entity: Dict[str, Any], result: Any) -> None:
    """Process the result for Endpoint plugin type"""
    endpoint_label, _, service_label = result
    entity["endpointLabel"] = endpoint_label
    entity["serviceLabel"] = service_label

def process_service_result(entity: Dict[str, Any], result: Any) -> None:
    """Process the result for Service plugin type"""
    service_label = result
    entity["serviceLabel"] = service_label

# Registry to map plugin types to their result processors
RESULT_PROCESSORS: Dict[str, Callable[[Dict[str, Any], Any], None]] = {
    "Endpoint": process_endpoint_result,
    "Service": process_service_result,
   
}

def get_plugin_type(plugin_id: str) -> Optional[str]:
    """
    Determine the plugin type from the plugin ID.
    
    Args:
        plugin_id: The plugin ID to check
        
    Returns:
        The plugin type if found, None otherwise
    """
    for plugin_type in PLUGIN_HANDLERS.keys():
        if plugin_type in plugin_id:
            return plugin_type
    return None

async def enrich_entity_ids_with_labels(
    prc: Dict[str, Any],
    seen_steady_ids: Set[Tuple[str, int]]
) -> None:
    """
    Enrich entity IDs in the probable root cause with labels.
    
    Args:
        prc: The probable root cause data to enrich
        seen_steady_ids: Set of already processed steady IDs to avoid duplicates
    """
    current_root_cause = prc.get("currentRootCause", [])
    if not isinstance(current_root_cause, list):
        logger.warning("currentRootCause is not a list, skipping enrichment")
        return

    tasks = []
    index_map = []

    # Prepare tasks for fetching labels
    for i, cause in enumerate(current_root_cause):
        entity = cause.get("entityID", {})
        plugin_id = entity.get("pluginId", "")
        steady_id = entity.get("steadyId")
        timestamp = cause.get("timestamp")
        
        if not steady_id or not timestamp:
            logger.debug(f"Missing steadyId or timestamp for cause at index {i}")
            continue

        # Skip already processed IDs
        key = (steady_id, timestamp)
        if key in seen_steady_ids:
            logger.debug(f"Skipping already processed steadyId: {steady_id}")
            continue
            
        seen_steady_ids.add(key)
        
        # Determine plugin type and get appropriate handler
        plugin_type = get_plugin_type(plugin_id)
        handler = PLUGIN_HANDLERS.get(plugin_type) if plugin_type else None
        
        # Create task if handler exists
        if handler:
            tasks.append(handler(steady_id, timestamp))
            index_map.append((i, plugin_type, steady_id, timestamp))
        else:
            logger.debug(f"No handler found for plugin_id: {plugin_id}")

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks) if tasks else []

    # Process results and update entities
    for idx, (i, plugin_type, steady_id, _) in enumerate(index_map):
        entity = current_root_cause[i].get("entityID", {})
        result = results[idx]
        
        # Process the result using the appropriate processor
        processor = RESULT_PROCESSORS.get(plugin_type)
        if processor:
            processor(entity, result)
        else:
            logger.warning(f"No result processor found for plugin_type: {plugin_type}")


async def process_incident(incident: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    
    trigger_id = incident.get("eventId", "")
    trigger_label = incident.get("entityLabel", "Unknown")
    prc = incident.get("probableCause", {})
    seen_steady_ids = set()

    # Enrich the PRC data with labels
    await enrich_entity_ids_with_labels(prc, seen_steady_ids)

    # Create the enriched entry
    entry = {
        "entityType": incident.get("entityType", ""),
        "problem": incident.get("problem", ""),
        "detail": incident.get("detail", ""),
        "probableCause": prc
    }

    key = f"Triggering Event ID: {trigger_id} | Triggering Entity Label: {trigger_label}"
    return key, entry


def save_output_to_file(output: Dict[str, Any], file_path: str) -> None:
    """
    Save the output data to a JSON file.
    
    Args:
        output: The data to save
        file_path: The path to save the file to
    """
    try:
        with open(file_path, "w") as f:
            json.dump(output, f, indent=4)
        logger.info(f"Output saved to {file_path}")
    except IOError as e:
        logger.error(f"Failed to save output to {file_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error saving output: {e}")


# === FastAPI Endpoints ===

@app.get("/prc-details")
async def fetch_prc_details():
    """
    Fetch and enrich PRC incident data with endpoint/service labels nested inside entityID.
    
    Returns:
        JSON response with enriched PRC data or error details
    """
    output = {}
    try:
        # Fetch and process incidents
        incidents_data = await fetch_incidents_data()
        logger.info(f"Fetched {len(incidents_data)} incidents")
        
        prc_incidents = filter_prc_incidents(incidents_data)
        logger.info(f"Found {len(prc_incidents)} PRC incidents")

        # Process all incidents concurrently
        results = await asyncio.gather(
            *[process_incident(incident) for incident in prc_incidents]
        )

        # Build output dictionary
        for key, entry in results:
            output[key] = entry

        # Save to file
        save_output_to_file(output, OUTPUT_FILE_PATH)
        
        return output

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=e.response.status_code, 
            content={"error": error_msg}
        )
    except httpx.RequestError as e:
        error_msg = f"Request error: {e}"
        logger.error(error_msg)
        return JSONResponse(status_code=503, content={"error": error_msg})
    except ValueError as e:
        error_msg = f"Value error: {e}"
        logger.error(error_msg)
        return JSONResponse(status_code=422, content={"error": error_msg})
    except Exception as e:
        error_msg = f"Failed to fetch PRC details: {e}"
        logger.exception(error_msg)
        return JSONResponse(status_code=500, content={"error": error_msg})



# === Main Entry Point ===

if __name__ == "__main__":
    import uvicorn
    
    # Configure uvicorn server
    uvicorn.run(
        "prc_label:app", 
        host="127.0.0.1", 
        port=8004, 
        reload=True,
        log_level="info"
    )