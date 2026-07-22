# Multi-stage build for GPU Cluster Validation Suite

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy source
COPY . /build

# Install Python dependencies
RUN pip install --no-cache-dir -e /build

# Stage 2: Runtime
FROM python:3.11-slim

LABEL maintainer="infrastructure-team@company.com"
LABEL description="GPU Cluster Acceptance & Validation Suite"

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    # NVIDIA tools (if available in container)
    # nvidia-utils \
    # InfiniBand tools (if available in container)
    # ibutils2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/gpu_cluster_validation /app/gpu_cluster_validation
COPY config /app/config

# Create reports directory
RUN mkdir -p /app/reports

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import gpu_cluster_validation; print('OK')" || exit 1

# Entry point
ENTRYPOINT ["gpu-cluster-validate"]
CMD ["--help"]
