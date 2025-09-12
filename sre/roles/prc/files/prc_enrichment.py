#!/usr/bin/env python3
"""
PRC Enrichment - pluginId- Type ENDPOINT, SERVICE, or INFRASTRUCTURE

This service fetches incident data with probable root causes (PRC) and enriches it
with endpoint, service, and infrastructure labels.
Please note taking into account pluginId of type Endpoint, Service, and Infrastructure
Includes metrics and tags directly in the main entity object for infrastructure plugins with related info of other snapshotIds
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
INFRASTRUCTURE_ENTITIES_URL = f"{BASE_URL}/api/infrastructure-monitoring/analyze/entities"

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
OUTPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "prc_label_v3.json")

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


async def get_infrastructure_details(snapshot_id: str, to_timestamp: int, pluginId: str) -> Dict[str, Any]:
    """
    Fetch infrastructure entity details for a given snapshot ID.
    
    Args:
        snapshot_id: The snapshot ID of the infrastructure entity
        to_timestamp: The timestamp to fetch metrics at
        pluginId: The plugin ID of the infrastructure entity
        
    Returns:
        A dictionary containing infrastructure entity details
    """
    if not snapshot_id:
        return {
            "label": "Unknown Infrastructure",
            "plugin": "Unknown",
            "time": to_timestamp,
            "relatedEntities": {
                "items": []
            }
        }
        
    try:
        # Determine the tag filter name based on the snapshot_id
        tag_filter_name = None
        
        # Check the snapshot_id to determine the appropriate tag filter
        if pluginId:
            if "host" in pluginId:
                tag_filter_name = "id.host"
            elif "process" in pluginId:
                tag_filter_name = "id.process"
            elif "opentelemetry" in pluginId:
                tag_filter_name = "id.otel"
            else:
                # If no specific pattern is matched, log a warning and use a fallback
                logger.warning(f"Unknown pluginId pattern: {pluginId}, using default tag filter")
                tag_filter_name = "id.host"  # Fallback only when no pattern is matched
        else:
            logger.warning("No pluginId provided, using default tag filter")
            tag_filter_name = "id.host"  # Fallback when pluginId is empty
                
        payload = {
            "tagFilterExpression": {
                "type": "TAG_FILTER",
                "name": tag_filter_name,
                "operator": "EQUALS",
                "entity": "NOT_APPLICABLE",
                "value": snapshot_id
            },
            "timeFrame": {
                "to": to_timestamp,
                "windowSize": METRICS_WINDOW_SIZE
            },
            "pagination": {
                "retrievalSize": 200
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(INFRASTRUCTURE_ENTITIES_URL, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if items:
                # Find the item with matching snapshot ID
                for item in items:
                    if item.get("snapshotId") == snapshot_id:
                        # Filter the items to only include specific fields and exclude the matching item
                        filtered_items = []
                        for related_item in items:
                            # Skip the item that matches the snapshot_id
                            if related_item.get("snapshotId") == snapshot_id:
                                continue
                                
                            filtered_item = {
                                "snapshotId": related_item.get("snapshotId"),
                                "label": related_item.get("label"),
                                "plugin": related_item.get("plugin"),
                                "time": related_item.get("time"),
                                "metrics": related_item.get("metrics", {}),
                                "tags": related_item.get("tags", {})
                            }
                            filtered_items.append(filtered_item)
                            
                        return {
                            "label": item.get("label", "Unknown Infrastructure"),
                            "plugin": item.get("plugin", "Unknown"),
                            "time": item.get("time", to_timestamp),
                            "metrics": item.get("metrics", {}),
                            "tags": item.get("tags", {}),
                            "relatedEntities": {
                                "items": filtered_items
                            }
                        }
                
                # If no exact match found, return the first item
                first_item = items[0]
                first_snapshot_id = first_item.get("snapshotId")
                
                # Filter the items to only include specific fields and exclude the first item
                filtered_items = []
                for related_item in items:
                    # Skip the first item
                    if related_item.get("snapshotId") == first_snapshot_id:
                        continue
                        
                    filtered_item = {
                        "snapshotId": related_item.get("snapshotId"),
                        "label": related_item.get("label"),
                        "plugin": related_item.get("plugin"),
                        "time": related_item.get("time"),
                        "metrics": related_item.get("metrics", {}),
                        "tags": related_item.get("tags", {})
                    }
                    filtered_items.append(filtered_item)
                    
                return {
                    "label": first_item.get("label", "Unknown Infrastructure"),
                    "plugin": first_item.get("plugin", "Unknown"),
                    "time": first_item.get("time", to_timestamp),
                    "metrics": first_item.get("metrics", {}),
                    "tags": first_item.get("tags", {}),
                    "relatedEntities": {
                        "items": filtered_items
                    }
                }
                
            logger.warning(f"No infrastructure details found for snapshot_id={snapshot_id}")
            return {
                "label": "Unknown Infrastructure",
                "plugin": "Unknown",
                "time": to_timestamp,
                "relatedEntities": {
                    "items": []
                }
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching infrastructure details for {snapshot_id}: {e.response.status_code}")
        return {
            "label": f"Error Infrastructure ({snapshot_id})",
            "plugin": "Unknown",
            "time": to_timestamp,
            "relatedEntities": {
                "items": []
            }
        }
    except httpx.RequestError as e:
        logger.error(f"Request error fetching infrastructure details for {snapshot_id}: {e}")
        return {
            "label": f"Error Infrastructure ({snapshot_id})",
            "plugin": "Unknown",
            "time": to_timestamp,
            "relatedEntities": {
                "items": []
            }
        }
    except Exception as e:
        logger.error(f"Error fetching infrastructure details for {snapshot_id}: {e}")
        return {
            "label": f"Error Infrastructure ({snapshot_id})",
            "plugin": "Unknown",
            "time": to_timestamp,
            "relatedEntities": {
                "items": []
            }
        }


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
    "Service": get_service_label,
    "Infrastructure": get_infrastructure_details
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

def process_infrastructure_result(entity: Dict[str, Any], result: Any) -> None:
    """Process the result for Infrastructure plugin type"""
    entity["infrastructureLabel"] = result.get("label", "Unknown Infrastructure")
    entity["infrastructurePlugin"] = result.get("plugin", "Unknown")
    entity["infrastructureTime"] = result.get("time", 0)
    # Include metrics and tags directly in the main entity object
    if "metrics" in result:
        entity["metrics"] = result.get("metrics", {})
    if "tags" in result:
        entity["tags"] = result.get("tags", {})
    if "relatedEntities" in result:
        entity["relatedEntities"] = result.get("relatedEntities")

# Registry to map plugin types to their result processors
RESULT_PROCESSORS: Dict[str, Callable[[Dict[str, Any], Any], None]] = {
    "Endpoint": process_endpoint_result,
    "Service": process_service_result,
    "Infrastructure": process_infrastructure_result
}

def get_plugin_type(plugin_id: str) -> Optional[str]:
    """
    Determine the plugin type from the plugin ID.
    
    Args:
        plugin_id: The plugin ID to check
        
    Returns:
        The plugin type if found, None otherwise
    """
    if "infrastructure" in plugin_id.lower():
        return "Infrastructure"
    
    for plugin_type in ["Endpoint", "Service"]:
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
        timestamp = cause.get("timestamp")
        
        if not timestamp:
            logger.debug(f"Missing timestamp for cause at index {i}")
            continue

        # Determine plugin type
        plugin_type = get_plugin_type(plugin_id)
        
        if not plugin_type:
            logger.debug(f"Unknown plugin type for plugin_id: {plugin_id}")
            continue
            
        # For infrastructure plugins, use snapshotId instead of steadyId
        if plugin_type == "Infrastructure":
            # Check if snapshotId is available in the current root cause
            snapshot_id = None
            for item in cause.get("explainability", []):
                if "relevantSnapshotID" in item:
                    snapshot_id = item.get("relevantSnapshotID")
                    break
                    
            if not snapshot_id:
                # If not found in explainability, check if it's directly in the cause
                snapshot_id = cause.get("snapshotId")
                
            if not snapshot_id:
                logger.debug(f"No snapshotId found for infrastructure plugin at index {i}")
                continue
                
            # Skip already processed IDs
            key = (snapshot_id, timestamp)
            if key in seen_steady_ids:
                logger.debug(f"Skipping already processed snapshotId: {snapshot_id}")
                continue
                
            seen_steady_ids.add(key)
            
            # Create task for infrastructure entity
            handler = PLUGIN_HANDLERS.get(plugin_type)
            if handler:
                tasks.append(handler(snapshot_id, timestamp, plugin_id))
                index_map.append((i, plugin_type, snapshot_id, timestamp))
            else:
                logger.debug(f"No handler found for plugin_type: {plugin_type}")
        else:
            # For non-infrastructure plugins, use steadyId as before
            steady_id = entity.get("steadyId")
            if not steady_id:
                logger.debug(f"Missing steadyId for cause at index {i}")
                continue
                
            # Skip already processed IDs
            key = (steady_id, timestamp)
            if key in seen_steady_ids:
                logger.debug(f"Skipping already processed steadyId: {steady_id}")
                continue
                
            seen_steady_ids.add(key)
            
            # Create task if handler exists
            handler = PLUGIN_HANDLERS.get(plugin_type)
            if handler:
                tasks.append(handler(steady_id, timestamp))
                index_map.append((i, plugin_type, steady_id, timestamp))
            else:
                logger.debug(f"No handler found for plugin_type: {plugin_type}")

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks) if tasks else []

    # Process results and update entities
    for idx, (i, plugin_type, id_value, _) in enumerate(index_map):
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
    Fetch and enrich PRC incident data with endpoint/service/infrastructure labels nested inside entityID.
    
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


# === CLI Entry Point for AWX ===
async def main():
    """
    Main entry point for CLI execution.
    Fetches and processes PRC data, then saves it to a file.
    """
    try:
        logger.info("Starting PRC enrichment process")
        
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
        output = {}
        for key, entry in results:
            output[key] = entry

        # Save to file
        save_output_to_file(output, OUTPUT_FILE_PATH)
        logger.info("PRC enrichment completed successfully")
        
        return output
    except Exception as e:
        logger.exception(f"Error in main function: {e}")
        return {"error": str(e)}

# === Main Entry Point ===

if __name__ == "__main__":
    if os.environ.get("RUN_MODE") == "api":
        import uvicorn
        # Configure uvicorn server
        uvicorn.run(
            "prc_enrichment:app", 
            host="127.0.0.1", 
            port=8004, 
            reload=True,
            log_level="info"
        )
    else:
        # Run in CLI mode
        asyncio.run(main())


