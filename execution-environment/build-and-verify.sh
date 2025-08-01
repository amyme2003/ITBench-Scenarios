#!/bin/bash

# Exit on error
set -e

echo "Building execution environment with Python 3.12..."
podman build -t ansible-ee:latest .

echo "Verifying Python version in the container..."
podman run --rm ansible-ee:latest python --version

echo "Verifying Ansible is installed..."
podman run --rm ansible-ee:latest ansible --version

echo "Success! The execution environment is ready."
echo "Follow the instructions in awx-ee-setup-guide.md to add this to AWX."

# Made with Bob
