#!/usr/bin/env python3
"""
CLI wrapper for prc_label.py to run it as a standalone script
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Import functions from prc_label.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from prc_label import fetch_incidents_data, filter_prc_incidents, process_incident

def save_output_to_file(output: Dict[str, Any], file_path: str) -> None:
    """
    Save the output data to a JSON file.
    
    Args:
        output: The data to save
        file_path: The path to save the file to
    """
    try:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(file_path, "w") as f:
            json.dump(output, f, indent=4)
        print(f"Output saved to {file_path}")
    except IOError as e:
        print(f"Failed to save output to {file_path}: {e}")
    except Exception as e:
        print(f"Unexpected error saving output: {e}")

async def main():
    """
    Main function to run the PRC label script and save the output to a file
    """
    # Get output path from environment variable or use default
    output_path = os.environ.get("OUTPUT_FILE_PATH", "prc_label_output.json")
    
    try:
        # Fetch and process incidents directly using the functions from prc_label.py
        print("Fetching incidents data...")
        incidents_data = await fetch_incidents_data()
        
        print("Filtering PRC incidents...")
        prc_incidents = filter_prc_incidents(incidents_data)
        
        print(f"Processing {len(prc_incidents)} PRC incidents...")
        output = {}
        
        # Process all incidents
        for incident in prc_incidents:
            key, entry = await process_incident(incident)
            output[key] = entry
        
        # Save the output to the specified file
        print(f"Saving output to {output_path}")
        save_output_to_file(output, output_path)
        
        print(f"PRC label data successfully saved to {output_path}")
        return 0
    except Exception as e:
        print(f"Error running PRC label script: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

# Made with Bob
