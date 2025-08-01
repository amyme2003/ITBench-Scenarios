# Ansible Execution Environment with Python 3.12

This document provides instructions for building and using the Ansible Execution Environment with Python 3.12 for AWX.

## Building the Execution Environment

```bash
# Build the image using Podman
cd execution-environment
podman build -t ansible-ee:latest .
```

## Pushing to a Container Registry

```bash
# Tag the image for your registry
podman tag ansible-ee:latest registry.example.com/ansible-ee:latest

# Login to your registry
podman login registry.example.com

# Push the image
podman push registry.example.com/ansible-ee:latest
```

## Configuring AWX to Use the Execution Environment

1. In AWX, navigate to **Administration > Execution Environments**
2. Click **Add** to create a new execution environment
3. Fill in the following details:
   - **Name**: Python 3.12 Execution Environment
   - **Image**: registry.example.com/ansible-ee:latest
   - **Pull**: Always pull container before running
4. Click **Save**

## Setting as Default Execution Environment

1. Navigate to **Settings > Jobs**
2. Set **Default Execution Environment** to your new execution environment
3. Click **Save**

## Verifying Python Version in AWX Jobs

Create a simple job template to verify the Python version:

1. Create a new project with a simple playbook:

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

2. Create a job template using this project
3. Select your new execution environment
4. Run the job and verify that it shows Python 3.12.x in the output

## Troubleshooting

If you encounter issues:

1. Verify the image can be pulled from your registry
2. Check AWX logs for any pull or execution errors
3. Ensure the Python 3.12 installation in the container is working correctly