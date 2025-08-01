FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    openssh-client \
    sshpass \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Ansible and other Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Verify Python version
RUN python -c "import sys; print(sys.version); assert sys.version_info >= (3, 12), 'Python version must be 3.12 or later'"

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN groupadd -r ansible && \
    useradd -r -g ansible -m ansible

# Create directories for Ansible
RUN mkdir -p /ansible/playbooks /ansible/collections && \
    chown -R ansible:ansible /ansible

# Set working directory
WORKDIR /ansible

# Switch to non-root user
USER ansible

# Set default command
CMD ["python", "-c", "import sys; print(f'Python {sys.version}')"]