# Docker Deployment Guide

This directory contains Docker and container orchestration setup for the GPU Cluster Validation Suite.

## Quick Start

### Build Docker Image

```bash
cd ..  # Go to project root
make docker-build
```

This creates image: `gpu-cluster-validation:latest`

### Run Validation in Container

```bash
docker run \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/reports:/app/reports \
  gpu-cluster-validation:latest \
  --cluster /app/config/cluster.example.yaml \
  --output /app/reports/
```

### Using Docker Compose

```bash
# Run full validation
docker-compose up

# Run specific command
docker-compose run validator --cluster /app/config/cluster.yaml --output /app/reports/

# View logs
docker-compose logs -f validator
```

## Production Deployment

### Prerequisites

- Docker/Podman installed
- Kubernetes cluster (optional)
- Network access from container to GPU cluster nodes
- SSH keys or credentials for cluster access (if required)

### Build & Tag for Registry

```bash
# Build
docker build -f docker/Dockerfile -t gpu-cluster-validation:v1.0.0 ..

# Tag for registry
docker tag gpu-cluster-validation:v1.0.0 \
  registry.company.com/ai-infrastructure/gpu-cluster-validation:v1.0.0

# Push
docker push registry.company.com/ai-infrastructure/gpu-cluster-validation:v1.0.0
```

## Kubernetes Deployment

### 1. Create Namespace

```bash
kubectl create namespace gpu-infrastructure
```

### 2. Create ConfigMap with Cluster Config

```bash
kubectl create configmap cluster-config \
  --from-file=config/cluster.yaml \
  -n gpu-infrastructure
```

### 3. Deploy as CronJob (Scheduled)

```yaml
# deployment/validation-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: gpu-cluster-validation
  namespace: gpu-infrastructure
spec:
  # Run daily at 2 AM UTC
  schedule: "0 2 * * *"
  
  # Keep last 3 successful and 1 failed job
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  
  jobTemplate:
    spec:
      backoffLimit: 3  # Retry up to 3 times
      
      template:
        metadata:
          labels:
            app: gpu-cluster-validation
            version: v1.0.0
        
        spec:
          serviceAccountName: gpu-validator
          
          # Tolerations for GPU nodes (if using node affinity)
          tolerations:
          - key: "gpu"
            operator: "Equal"
            value: "true"
            effect: "NoSchedule"
          
          containers:
          - name: validator
            image: registry.company.com/ai-infrastructure/gpu-cluster-validation:v1.0.0
            imagePullPolicy: IfNotPresent
            
            command:
            - gpu-cluster-validate
            
            args:
            - --cluster=/config/cluster.yaml
            - --output=/reports
            - --log-level=INFO
            
            # Resource requests/limits
            resources:
              requests:
                cpu: 2
                memory: 2Gi
              limits:
                cpu: 4
                memory: 4Gi
            
            # Volume mounts
            volumeMounts:
            - name: config
              mountPath: /config
              readOnly: true
            
            - name: reports
              mountPath: /reports
            
            # Optional: mount host network for IB access
            # - name: infiniband
            #   mountPath: /sys/class/infiniband
            #   readOnly: true
            
            # Environment
            env:
            - name: LOG_LEVEL
              value: "INFO"
            - name: PYTHONUNBUFFERED
              value: "1"
          
          # Optional: node selector for GPU infrastructure nodes
          nodeSelector:
            kubernetes.io/hostname: "gpu-infra-01"
          
          # Volumes
          volumes:
          - name: config
            configMap:
              name: cluster-config
          
          - name: reports
            emptyDir: {}
          
          # Optional: InfiniBand volume
          # - name: infiniband
          #   hostPath:
          #     path: /sys/class/infiniband
          #     type: Directory
          
          # Cleanup policy
          restartPolicy: OnFailure
          
          # Cleanup after job completes
          ttlSecondsAfterFinished: 86400  # 24 hours
```

Deploy:

```bash
kubectl apply -f deployment/validation-cronjob.yaml
```

### 4. Deploy as Job (One-time)

```yaml
# deployment/validation-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: gpu-cluster-validation-$(date +%s)
  namespace: gpu-infrastructure
spec:
  template:
    spec:
      serviceAccountName: gpu-validator
      
      containers:
      - name: validator
        image: registry.company.com/ai-infrastructure/gpu-cluster-validation:v1.0.0
        
        args:
        - --cluster=/config/cluster.yaml
        - --output=/reports
        
        volumeMounts:
        - name: config
          mountPath: /config
        - name: reports
          mountPath: /reports
      
      volumes:
      - name: config
        configMap:
          name: cluster-config
      - name: reports
        emptyDir: {}
      
      restartPolicy: Never
  
  backoffLimit: 3
```

Deploy:

```bash
kubectl apply -f deployment/validation-job.yaml
```

### 5. Create ServiceAccount (RBAC)

```yaml
# deployment/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: gpu-validator
  namespace: gpu-infrastructure

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: gpu-validator
rules:
- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: gpu-validator
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: gpu-validator
subjects:
- kind: ServiceAccount
  name: gpu-validator
  namespace: gpu-infrastructure
```

Apply:

```bash
kubectl apply -f deployment/rbac.yaml
```

## Monitoring Integration

### Prometheus Metrics

The validation suite exposes metrics on `/metrics`:

```yaml
# prometheus-scrape-config.yaml
global:
  scrape_interval: 60s

scrape_configs:
- job_name: gpu-validation
  static_configs:
  - targets: ['localhost:8000']  # Or pod IP
  metrics_path: '/metrics'
```

### Example Metrics

```
gpu_validation_duration_seconds{cluster="us-west-2a"} 45.23
gpu_validation_phase_duration_seconds{phase="1",name="hardware_inventory"} 5.12
gpu_validation_checks_total{status="pass"} 45
gpu_validation_checks_total{status="fail"} 2
gpu_cluster_health_score{cluster="us-west-2a"} 95.5
```

## Logs and Debugging

### View Container Logs

```bash
# Docker
docker logs $(docker ps | grep validator | awk '{print $1}')

# Kubernetes
kubectl logs -n gpu-infrastructure job/gpu-cluster-validation

# Follow logs
kubectl logs -n gpu-infrastructure job/gpu-cluster-validation -f
```

### Debug Mode

Run with debug logging:

```bash
docker run \
  -e LOG_LEVEL=DEBUG \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/reports:/app/reports \
  gpu-cluster-validation:latest \
  --cluster /app/config/cluster.yaml --log-level DEBUG
```

### Access Reports

```bash
# Docker Compose
docker-compose run validator cat /app/reports/validation_report_*.html

# Kubernetes
kubectl cp gpu-infrastructure/pod-name:/app/reports ./reports
```

## Network Considerations

### For GPU Cluster Access

The container needs network access to cluster nodes. Options:

1. **Host Network** (direct access)
```yaml
spec:
  hostNetwork: true  # Use host networking
```

2. **Network Policy** (restricted)
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gpu-validator
spec:
  podSelector:
    matchLabels:
      app: gpu-cluster-validation
  
  policyTypes:
  - Egress
  
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 22      # SSH
    - protocol: TCP
      port: 636     # LDAP over TLS
    - protocol: TCP
      port: 16500   # InfiniBand management
```

3. **Service Mesh** (Istio/Linkerd)
```bash
kubectl label namespace gpu-infrastructure istio-injection=enabled
```

## Storage Considerations

### Persistent Reports

To keep reports after pod deletion:

```yaml
spec:
  volumes:
  - name: reports
    persistentVolumeClaim:
      claimName: validation-reports-pvc
```

Create PVC:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: validation-reports-pvc
  namespace: gpu-infrastructure
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Validate GPU Cluster

on:
  schedule:
    - cron: '0 2 * * *'  # Daily 2 AM UTC
  workflow_dispatch:

jobs:
  validate:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: make docker-build
    
    - name: Run validation
      run: |
        docker run \
          -v $(pwd)/config:/app/config:ro \
          -v $(pwd)/reports:/app/reports \
          gpu-cluster-validation:latest \
          --cluster /app/config/cluster.yaml
    
    - name: Upload report
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: validation-report
        path: reports/
    
    - name: Notify Slack
      if: failure()
      uses: slackapi/slack-github-action@v1
      with:
        payload: |
          {
            "text": "GPU Cluster Validation FAILED"
          }
```

## Troubleshooting

### Container Can't Access Cluster

Check network:

```bash
# From inside container
docker exec <container-id> ping <cluster-node>
docker exec <container-id> nc -zv <cluster-node> 22
```

### Mocked Hardware vs Real Hardware

Services default to mocked mode for testing. To use real hardware:

```bash
# Export flag or modify code
docker run \
  -e USE_REAL_HARDWARE=true \
  gpu-cluster-validation:latest \
  ...
```

### Memory Issues

Increase limits:

```bash
docker run \
  -m 8g \
  gpu-cluster-validation:latest \
  ...
```

## Performance Tuning

### Multi-stage Build

The Dockerfile uses multi-stage builds to minimize image size:

```
Base image: python:3.11-slim (150 MB)
+ deps + code: ~200 MB total
Result: ~200 MB final image
```

### Layer Caching

Layers are ordered for better Docker cache:

```
1. Base image (cacheable)
2. Install dependencies (reuse if unchanged)
3. Copy code (frequently changes)
```

Rebuild only changes layers 3.

## Questions?

Contact: infrastructure-team@company.com
