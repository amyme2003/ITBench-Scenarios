# PRC Label Role

This role contains the Python script that fetches incident data with probable root causes (PRC) and enriches it with endpoint and service labels.

## Requirements

- Python 3.6+
- Required Python packages (installed in the execution environment):
  - fastapi
  - httpx
  - uvicorn
  - pandas
  - python-dotenv

## Files

- `files/prc_label.py`: The main Python script that fetches and enriches PRC data
- `files/requirements.txt`: Python package dependencies

## Usage

This script is designed to be run in an AWX execution environment. The execution environment should include:
- The Python script at `/runner/prc_label.py`
- The `.env` file at `/runner/.env` with the required environment variables:
  - `INSTANA_API_TOKEN`
  - `INSTANA_API_ENDPOINT`

## Output

The script generates a JSON file with enriched PRC data.