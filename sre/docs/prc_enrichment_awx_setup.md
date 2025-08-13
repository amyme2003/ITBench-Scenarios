# PRC Enrichment AWX Setup

This document describes how to set up the Probable Root Cause (PRC) enrichment pipeline in AWX.

## Overview

The PRC enrichment pipeline fetches incidents with probable root causes from Instana and enriches them with endpoint and service labels. The pipeline is implemented as an AWX job template that can be run on demand or scheduled.

## Prerequisites

- AWX instance up and running
- Admin access to AWX
- Instana API token with appropriate permissions

## Automated Setup

We provide an Ansible playbook that automates the setup of the AWX pipeline. The playbook creates:

1. A project that pulls from a Git repository
2. An inventory with a localhost host
3. A job template with a survey for configuring the pipeline

### Running the Setup Playbook

```bash
ansible-playbook sre/playbooks/setup_awx_prc_pipeline.yaml -e "awx_host=http://your-awx-host awx_username=your-username awx_password=your-password"
```

Replace `your-awx-host`, `your-username`, and `your-password` with your AWX instance details.

## Manual Setup

If you prefer to set up the pipeline manually, follow these steps:

1. Log in to your AWX instance
2. Create a new project:
   - Name: PRC Enrichment Project
   - SCM Type: Git
   - SCM URL: https://github.com/ansible/ansible-tower-samples.git
   - SCM Branch: master
   - Update on Launch: Yes
3. Create a new inventory:
   - Name: Default Inventory
   - Add a host: localhost
   - Set the host's variables: `ansible_connection: local`
4. Create a new job template:
   - Name: PRC Enrichment Pipeline
   - Inventory: Default Inventory
   - Project: PRC Enrichment Project
   - Playbook: hello_world.yml
   - Extra Variables:
     ```yaml
     instana_api_endpoint: "https://release-instana.instana.rocks"
     instana_api_token: ""
     output_dir: "/tmp/prc_enrichment_results"
     output_filename: "prc_label.json"
     ```
   - Enable Survey
   - Add survey questions:
     - Instana API Endpoint (text)
     - Instana API Token (password)
     - Output Directory (text)
     - Output Filename (text)

## Running the Pipeline

To run the pipeline:

1. Log in to AWX
2. Navigate to Templates
3. Find the "PRC Enrichment Pipeline" template
4. Click the rocket icon to launch
5. Fill in the survey questions:
   - Instana API Endpoint: The URL of your Instana API
   - Instana API Token: Your Instana API token
   - Output Directory: Directory where the enriched data will be saved
   - Output Filename: Filename for the enriched data
6. Click Launch

## Customizing the Pipeline

The current implementation uses a sample playbook from the Ansible Tower samples repository. To customize the pipeline with our specific PRC enrichment logic, you would need to:

1. Create a Git repository with your custom playbooks
2. Update the project in AWX to point to your repository
3. Update the job template to use your custom playbook

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Ensure your AWX credentials are correct
2. **Project Sync Failures**: Check that the Git repository is accessible
3. **Job Execution Failures**: Verify that the playbook exists in the repository
4. **API Connection Issues**: Confirm that the Instana API endpoint is reachable and the token is valid

### Logs

To troubleshoot issues:

1. Check the job output in AWX
2. Examine the AWX server logs
3. For project sync issues, check the project update logs

## Next Steps

- Schedule the pipeline to run periodically
- Set up notifications for job success/failure
- Integrate with other systems to consume the enriched data