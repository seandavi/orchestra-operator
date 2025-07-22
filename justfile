# Kubernetes development tasks

# Default Kubernetes version and cluster name
k8s_version := "v1.28.0"
cluster_name := "orchestra-test"

# List available commands
default:
    @just --list

# Create kind cluster for development
cluster-up version=k8s_version name=cluster_name:
    #!/usr/bin/env bash
    echo "Creating kind cluster '{{name}}' with Kubernetes {{version}}"
    kind create cluster --name {{name}} --image kindest/node:{{version}}
    kubectl cluster-info --context kind-{{name}}

# Delete kind cluster
cluster-down name=cluster_name:
    kind delete cluster --name {{name}}

# Reset cluster (delete and recreate)
cluster-reset version=k8s_version name=cluster_name: (cluster-down name) (cluster-up version name)

# Load operator image into cluster
load-image name=cluster_name image="orchestra-operator:latest":
    kind load docker-image {{image}} --name {{name}}

# Install CRDs and deploy operator
deploy: build-image load-image
    kubectl apply -f config/crd/
    kubectl apply -f config/deploy/

# Build operator Docker image
build-image:
    docker build -t orchestra-operator:latest .

# Install Python dependencies
install-deps:
    uv sync

# Run operator locally (for development)
run-local:
    cd src && python -m main

# Apply CRDs to cluster
apply-crd:
    kubectl apply -f config/crd/

# Run tests against cluster
test:
    pytest tests/ -v

# Setup development environment
dev-setup: cluster-up deploy
    echo "Development environment ready!"

# CI/CD setup (lightweight)
ci-setup version=k8s_version:
    just cluster-up {{version}} ci-cluster
    just load-image ci-cluster