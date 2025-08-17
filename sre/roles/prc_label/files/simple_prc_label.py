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
if os.path.isabs(safe_path) and (safe_path.startswith("/tmp/") or os.access(os.path.dirname(safe_path), os.W_OK)):
    # Save the output to a file
    with open(safe_path, "w") as f:
        json.dump(output, f, indent=4)
    
    print(f"Output saved to {output_path}")
else:
    print(f"Error: Invalid output path {output_path}")

# Made with Bob
