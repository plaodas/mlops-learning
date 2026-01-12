# MinIO port-forward container

This lightweight image runs `kubectl port-forward -n argo svc/minio 9000:9000` in a loop and restarts on failure.

Build
```
docker build -t minio-pf:latest docker/minio-pf
```

Run (using your kubeconfig)
```
docker run -d --name minio-pf --restart unless-stopped \
  -v $HOME/.kube:/root/.kube:ro \
  --network host \
  minio-pf:latest
```

Notes
- Mount a kubeconfig so the container can authenticate to the cluster (`/root/.kube/config`).
- `--network host` makes `localhost:9000` on the host connect to the forwarded port; if you prefer not to use host networking, remove it and ensure port mapping/security allow access.
- Alternatively run the container with docker-compose and appropriate restart policy.
