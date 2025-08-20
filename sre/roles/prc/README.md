# PRC Role

This role runs a Python script to fetch Probable Root Cause (PRC) data from Instana and stores the JSON output as a job artifact in AWX.

## Requirements

- Python 3.6+
- Instana API token with appropriate permissions
- AWX for job execution and artifact storage

## Dependencies

The following Python packages are required:
- fastapi
- httpx
- uvicorn
- pandas
- python-dotenv

These will be automatically installed by the role.

## Role Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| instana_api_token | Instana API token for authentication | Yes | - |

## Example Playbook

```yaml
- name: Fetch PRC data from Instana
  hosts: localhost
  connection: local
  gather_facts: false
  
  tasks:
    - name: Import PRC role
      ansible.builtin.import_role:
        name: ../roles/prc
      vars:
        instana_api_token: "{{ instana_api_token }}"
```

## AWX Setup

1. Create a new job template in AWX
2. Set the playbook to `sre/playbooks/manage_prc.yaml`
3. Add the Instana API token as an **Extra Variable**:
   ```yaml
   instana_api_token: "your-api-token-here"
   ```
   Note: For security, consider using AWX's built-in encryption for this variable
4. Enable "Use Fact Cache" to store the JSON output as a job artifact

Alternatively, you can use environment variables by:
1. In the job template, under "Extra Variables", add:
   ```yaml
   ansible_environment:
     INSTANA_API_TOKEN: "your-api-token-here"
   ```

## Output

The role will store the PRC data as a JSON artifact in the AWX job details under the key `prc_data_json`.