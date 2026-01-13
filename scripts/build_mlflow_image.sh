#!/bin/sh
set -e
# Build and push mlflow image with boto3 to local registry used for kind
IMAGE_NAME=localhost:5001/mlflow:with-boto3
docker build -t "$IMAGE_NAME" -f docker/mlflow/Dockerfile .
# If you run a local registry (localhost:5001), push; otherwise load into kind:
if docker info >/dev/null 2>&1; then
  echo "Pushing $IMAGE_NAME to local registry"
  docker push "$IMAGE_NAME" || echo "push failed — ensure registry at localhost:5001 is running"
fi
# For kind clusters without registry, user can run:
# kind load docker-image $IMAGE_NAME --name <cluster-name>

echo "Built image: $IMAGE_NAME"
