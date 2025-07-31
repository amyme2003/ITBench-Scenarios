FROM debian:bookworm-slim@sha256:d2a1f0c8a9d42f05f01a2b5a8b1bf1bfbf7793a2bac56d07e50c90b4ba8b3f7b

# Install Python 3.12 and system dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    gcc \
    git \
    curl \
    openssh-client \
    sshpass \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set a non-root user
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} ansible && \
    useradd -u ${USER_ID} -g ansible -m ansible

# Set up working directory
WORKDIR /ansible

# Create and activate virtual environment
RUN python3.12 -m venv /ansible/venv
ENV PATH="/ansible/venv/bin:$PATH"
ENV VIRTUAL_ENV="/ansible/venv"

# Copy requirements file
COPY requirements.txt .

# Install Ansible and other Python dependencies in the virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Verify Python version meets the requirement (3.12 or later)
RUN python -c "import sys; assert sys.version_info >= (3, 12), 'Python version must be 3.12 or later'"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ANSIBLE_PYTHON_INTERPRETER=/ansible/venv/bin/python

# Create directories for Ansible
RUN mkdir -p /ansible/playbooks /ansible/collections && \
    chown -R ansible:ansible /ansible

# Switch to non-root user
USER ansible

# Set default command
CMD ["ansible-playbook", "--version"]