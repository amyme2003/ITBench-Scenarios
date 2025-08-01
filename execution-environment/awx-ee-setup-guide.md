# Adding the Execution Environment to AWX

This guide provides step-by-step instructions for adding the Python 3.12 execution environment to AWX.

## Option 1: Using the AWX Web UI

1. **Build and Push the Image**:
   ```bash
   # Build the image
   cd execution-environment
   podman build -t ansible-ee:latest .
   
   # Tag for your registry (replace with your actual registry)
   podman tag ansible-ee:latest registry.example.com/ansible-ee:latest
   
   # Login to your registry
   podman login registry.example.com
   
   # Push the image
   podman push registry.example.com/ansible-ee:latest
   ```

2. **Add the Execution Environment in AWX**:
   - Log in to your AWX web interface
   - Navigate to **Administration > Execution Environments**
   - Click the **Add** button
   - Fill in the form:
     - **Name**: Python 3.12 Execution Environment
     - **Image**: registry.example.com/ansible-ee:latest
     - **Pull Policy**: Always pull container before running
     - **Description**: Custom execution environment with Python 3.12
   - Click **Save**

3. **Set as Default (Optional)**:
   - Navigate to **Settings > Jobs**
   - Set **Default Execution Environment** to your new execution environment
   - Click **Save**

## Option 2: Using the AWX API

1. **Build and Push the Image** (same as Option 1)

2. **Create the Execution Environment via API**:
   ```bash
   # Replace with your AWX details
   AWX_HOST="https://your-awx-host"
   AWX_USER="admin"
   AWX_PASSWORD="password"
   
   # Create the execution environment
   curl -k -X POST \
     -u "${AWX_USER}:${AWX_PASSWORD}" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Python 3.12 Execution Environment",
       "image": "registry.example.com/ansible-ee:latest",
       "pull": "always",
       "description": "Custom execution environment with Python 3.12"
     }' \
     "${AWX_HOST}/api/v2/execution_environments/"
   ```

## Option 3: Using the AWX CLI (awx-cli)

1. **Build and Push the Image** (same as Option 1)

2. **Install awx-cli if not already installed**:
   ```bash
   pip install awxkit
   ```

3. **Create the Execution Environment**:
   ```bash
   # Configure awx-cli
   awx config --host https://your-awx-host --username admin --password password
   
   # Create the execution environment
   awx execution_environments create \
     --name "Python 3.12 Execution Environment" \
     --image "registry.example.com/ansible-ee:latest" \
     --pull "always" \
     --description "Custom execution environment with Python 3.12"
   ```

## Using the Execution Environment

Once added, you can use the execution environment in several ways:

1. **For a Specific Job Template**:
   - Edit the job template
   - Under **Execution Environment**, select your new execution environment
   - Save the job template

2. **For a Project**:
   - Edit the project
   - Under **Execution Environment**, select your new execution environment
   - Save the project

3. **For an Inventory**:
   - Edit the inventory
   - Under **Execution Environment**, select your new execution environment
   - Save the inventory

4. **For an Organization**:
   - Edit the organization
   - Under **Default Execution Environment**, select your new execution environment
   - Save the organization

## Verifying the Setup

Create a simple job template with this playbook to verify Python version:

```yaml
---
- name: Verify Python version
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Check Python version
      ansible.builtin.command: python -c "import sys; print(sys.version)"
      register: python_version
      
    - name: Display Python version
      ansible.builtin.debug:
        var: python_version.stdout
```

Run the job template and check the output to confirm it's using Python 3.12.