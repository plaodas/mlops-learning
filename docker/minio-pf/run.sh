#!/bin/sh
set -e

echo "Starting kubectl port-forward loop for MinIO (svc/minio in namespace 'argo')"
while true; do
  kubectl port-forward -n argo svc/minio 9000:9000 --address 0.0.0.0
  echo "port-forward exited unexpectedly; restarting in 5s..."
  sleep 5
done
