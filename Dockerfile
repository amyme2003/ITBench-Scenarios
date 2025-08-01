FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV ANSIBLE_PYTHON_INTERPRETER=/usr/local/bin/python

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        git \
        curl \
        jq \
        make \
        build-essential \
        libffi-dev \
        libssl-dev \
        openssh-client \
        sshpass \
        unzip \
        wget \
        gnupg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify Python version meets the requirement (3.12 or later)
RUN python --version && \
    python -c "import sys; assert sys.version_info >= (3, 12), 'Python version must be 3.12 or later'"

# Install Ansible and other Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ansible ansible-runner kubernetes openshift PyYAML jmespath netaddr boto3 botocore requests cryptography

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws

# Install Helm
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/

# Install kops
RUN curl -Lo /usr/local/bin/kops https://github.com/kubernetes/kops/releases/latest/download/kops-linux-amd64 && \
    chmod +x /usr/local/bin/kops

# Create directories for Ansible
RUN mkdir -p /ansible/playbooks /ansible/collections

WORKDIR /ansible

# Set default command
CMD ["ansible-runner", "--version"]
