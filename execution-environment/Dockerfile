FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    openssh-client \
    sshpass \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /ansible

# Install Ansible and other Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ansible kubernetes openshift PyYAML jmespath netaddr boto3 botocore requests cryptography

# Verify Python version meets the requirement (3.12 or later)
RUN python -c "import sys; assert sys.version_info >= (3, 12), 'Python version must be 3.12 or later'"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ANSIBLE_PYTHON_INTERPRETER=/usr/local/bin/python

# Create directories for Ansible
RUN mkdir -p /ansible/playbooks /ansible/collections

# Set default command
CMD ["ansible-playbook", "--version"]