# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set working directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    jq \
    vim \
    nano \
    htop \
    tree \
    unzip \
    zip \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python development tools
RUN pip install --no-cache-dir \
    pip-tools \
    black \
    isort \
    pylint \
    pytest \
    pytest-cov \
    requests \
    pyyaml \
    pandas \
    streamlit \
    fastapi \
    uvicorn \
    minio \
    psycopg2-binary \
    pydantic-settings

# All development dependencies are already installed above

# Create a non-root user
RUN useradd -m -s /bin/bash developer && \
    usermod -aG sudo developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set up git configuration
RUN git config --global init.defaultBranch main && \
    git config --global pull.rebase false

# Create development scripts directory
RUN mkdir -p /workspace/scripts

# Set up environment
ENV PYTHONPATH=/workspace
ENV DEVELOPMENT=true
ENV PATH="/workspace/scripts:$PATH"

# Switch to non-root user
USER developer

# Keep container running
CMD ["sleep", "infinity"]
