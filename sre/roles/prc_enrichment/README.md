# PRC Enrichment

This role provides functionality to fetch incident data with probable root causes (PRC) from Instana and enrich it with endpoint and service labels.

## Overview

The PRC Enrichment script connects to the Instana API, retrieves incidents with probable root causes, and enriches them with additional information such as endpoint labels and service labels. This helps in better understanding and analyzing incidents.

## Requirements

- Python 3.8 or higher
- Required Python packages (installed automatically):
  - fastapi
  - httpx
  - uvicorn
  - pandas
  - python-dotenv

## Usage

### Direct Script Execution

You can run the PRC enrichment script directly using the provided shell script:

```bash
cd files
./run_prc_enrichment.sh --token YOUR_INSTANA_API_TOKEN
```

Or with environment variables:

```bash
export INSTANA_API_TOKEN="your-token"
./run_prc_enrichment.sh
```

By default, results will be saved to `~/prc_enrichment_results/prc_label.json`.

### Ansible Playbook

You can run the PRC enrichment using the provided Ansible playbook:

```bash
ansible-playbook ../../playbooks/run_prc_enrichment.yaml -e "instana_api_token=YOUR_TOKEN"
```

### AWX Integration

This role can be integrated with AWX for scheduled execution. See the documentation in `sre/docs/prc_enrichment_awx_setup.md` for detailed setup instructions.

## Configuration

The following variables can be configured:

| Variable | Description | Default |
|----------|-------------|---------|
| `instana_api_endpoint` | Instana API endpoint URL | https://release-instana.instana.rocks |
| `instana_api_token` | Instana API token | (required) |
| `output_dir` | Directory where the enriched PRC data will be saved | ~/prc_enrichment_results |
| `output_filename` | Filename for the enriched PRC data | prc_label.json |

## Directory Structure

```
prc_enrichment/
├── defaults/
│   └── main/
│       └── main.yaml         # Default variables
├── files/
│   ├── prc_enrichment.py     # Main Python script
│   ├── requirements.txt      # Python dependencies
│   └── run_prc_enrichment.sh # Shell script for direct execution
├── tasks/
│   └── main.yaml             # Ansible tasks
├── templates/
│   └── prc_env.j2            # Environment file template
└── README.md                 # This file
```

## Output

The script generates a JSON file containing enriched incident data with probable root causes. The output includes:

- Incident details (entity type, problem, detail)
- Probable cause information
- Enriched endpoint and service labels

Example output:

```json
{
  "Triggering Event ID: 12345 | Triggering Entity Label: api-service": {
    "entityType": "service",
    "problem": "High latency",
    "detail": "Service experiencing high latency",
    "probableCause": {
      "found": true,
      "currentRootCause": [
        {
          "entityID": {
            "pluginId": "com.instana.plugin.service",
            "steadyId": "abcd1234",
            "endpointLabel": "/api/v1/users",
            "serviceLabel": "user-service"
          },
          "timestamp": 1628097600000
        }
      ]
    }
  }
}
```

## Security Considerations

- The Instana API token is sensitive information and should be handled securely
- In AWX, use the built-in credential management system
- For local development, use environment variables or a `.env` file (which is excluded from Git)
- Never hardcode the token in any files that might be committed to the repository

## License

This project is licensed under the MIT License.