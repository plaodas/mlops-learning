This directory contains a patched copy of the Bitnami `minio` Helm chart used
locally to avoid duplicate `MINIO_BROWSER` env entries when setting that value
from `values.yaml`.

Notes:
- The chart depends on the `common` chart from the Bitnami charts OCI registry.
- We only include the minimal files required to reproduce the template patch
  (the full upstream chart contains many more files).
- Use this chart via:

```bash
helm upgrade --install minio ./charts/minio -n argo -f minio-values.yaml
```

If you want the full upstream chart, use `helm pull bitnami/minio --untar`.
