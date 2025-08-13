#!/bin/bash
# Simple script to run PRC enrichment directly

# Default values
INSTANA_API_ENDPOINT=${INSTANA_API_ENDPOINT:-"https://release-instana.instana.rocks"}
INSTANA_API_TOKEN=${INSTANA_API_TOKEN:-""}
OUTPUT_DIR=${OUTPUT_DIR:-"$HOME/prc_enrichment_results"}
OUTPUT_FILENAME=${OUTPUT_FILENAME:-"prc_label.json"}
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_FILENAME"

# Help function
function show_help {
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  -e, --endpoint URL    Instana API endpoint (default: $INSTANA_API_ENDPOINT)"
  echo "  -t, --token TOKEN     Instana API token (required if not set as env var)"
  echo "  -d, --dir PATH        Output directory (default: $OUTPUT_DIR)"
  echo "  -f, --filename NAME   Output filename (default: $OUTPUT_FILENAME)"
  echo "  -h, --help            Show this help message"
  echo ""
  echo "Environment variables:"
  echo "  INSTANA_API_ENDPOINT  Instana API endpoint"
  echo "  INSTANA_API_TOKEN     Instana API token"
  echo "  OUTPUT_DIR            Output directory"
  echo "  OUTPUT_FILENAME       Output filename"
  echo ""
  echo "Example:"
  echo "  $0 --token abc123 --dir /path/to/results --filename results.json"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -e|--endpoint)
      INSTANA_API_ENDPOINT="$2"
      shift
      shift
      ;;
    -t|--token)
      INSTANA_API_TOKEN="$2"
      shift
      shift
      ;;
    -d|--dir)
      OUTPUT_DIR="$2"
      shift
      shift
      ;;
    -f|--filename)
      OUTPUT_FILENAME="$2"
      shift
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# Update OUTPUT_PATH with the latest values
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_FILENAME"

# Check if token is provided
if [ -z "$INSTANA_API_TOKEN" ]; then
  echo "Error: Instana API token is required"
  echo "Please provide it using the --token option or set the INSTANA_API_TOKEN environment variable"
  exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"
if [ $? -ne 0 ]; then
  echo "Error: Failed to create output directory: $OUTPUT_DIR"
  exit 1
fi

# Check if Python and required packages are installed
echo "Checking Python and required packages..."
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" || {
  echo "Error: Python 3.8 or higher is required"
  exit 1
}

# Install required packages if not already installed
pip install --quiet fastapi httpx uvicorn pandas python-dotenv || {
  echo "Error: Failed to install required Python packages"
  exit 1
}

# Set environment variables for the script
export INSTANA_API_ENDPOINT="$INSTANA_API_ENDPOINT"
export INSTANA_API_TOKEN="$INSTANA_API_TOKEN"
export PRC_OUTPUT_FILE="$OUTPUT_PATH"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the PRC enrichment script
echo "Running PRC enrichment script..."
echo "API Endpoint: $INSTANA_API_ENDPOINT"
echo "Output Path: $OUTPUT_PATH"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Check if the script exists in the current directory or script directory
if [ -f "./prc_enrichment.py" ]; then
  python ./prc_enrichment.py
elif [ -f "$SCRIPT_DIR/prc_enrichment.py" ]; then
  python "$SCRIPT_DIR/prc_enrichment.py"
else
  echo "Error: prc_enrichment.py not found"
  exit 1
fi

# Check if the output file was created
if [ -f "$OUTPUT_PATH" ]; then
  echo "PRC enrichment completed successfully"
  echo "Results saved to: $OUTPUT_PATH"
else
  echo "Error: Output file was not created"
  exit 1
fi

# Made with Bob
