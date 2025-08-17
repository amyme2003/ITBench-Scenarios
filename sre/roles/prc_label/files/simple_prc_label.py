"""
Simple PRC Label script that creates a basic JSON output file
"""

import json
import os
import time

# Create a simple JSON output
output = {
    "message": "This is a simple PRC label output",
    "timestamp": time.time(),
    "status": "success"
}

# Define the output path (use environment variable if available)
output_path = os.environ.get("PRC_OUTPUT_PATH", "/tmp/prc_label.json")

# Validate the path before opening
safe_path = os.path.normpath(output_path)
try:
    # Create directory if it doesn't exist
    output_dir = os.path.dirname(safe_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    # Save the output to a file
    with open(safe_path, "w") as f:
        json.dump(output, f, indent=4)
    
    print(f"Output saved to {output_path}")
except (IOError, PermissionError) as e:
    print(f"Error: Cannot write to output path {output_path}: {e}")
except Exception as e:
    print(f"Error: Unexpected error with output path {output_path}: {e}")

# Made with Bob
