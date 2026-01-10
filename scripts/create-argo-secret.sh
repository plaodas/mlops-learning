#!/usr/bin/env bash
set -euo pipefail

# Create TLS cert/key for argo.local and create/update Kubernetes secret argo-tls
# Usage: ./create-argo-secret.sh [--force]
# --force : delete existing secret before creating

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_PATH="$SCRIPT_DIR/argo.local.pem"
KEY_PATH="$SCRIPT_DIR/argo.local-key.pem"
NAMESPACE="argo"
SECRET_NAME="argo-tls"
FORCE=0

usage(){
  echo "Usage: $0 [--force|-f]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|-f) FORCE=1; shift;;
    -h|--help) usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

# Generate certs using mkcert if available, otherwise fallback to openssl (self-signed, not trusted)
if command -v mkcert >/dev/null 2>&1; then
  echo "mkcert found — generating certificate for argo.local"
  mkcert -install || true
  mkcert argo.local
  # mkcert outputs files in current dir named argo.local.pem and argo.local-key.pem
  mv argo.local.pem "$CERT_PATH" 2>/dev/null || true
  mv argo.local-key.pem "$KEY_PATH" 2>/dev/null || true
else
  echo "mkcert not found — generating self-signed certificate with openssl (NOT system-trusted)"
  TMPCNF=$(mktemp)
  cat > "$TMPCNF" <<'EOF'
[req]
distinguished_name=req
prompt=no
[req_distinguished_name]
CN=argo.local
[v3_req]
subjectAltName=DNS:argo.local
EOF
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 -keyout "$KEY_PATH" -out "$CERT_PATH" -config "$TMPCNF" -extensions v3_req
  rm -f "$TMPCNF"
fi

if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
  echo "Error: certificate or key not found. Expected: $CERT_PATH and $KEY_PATH"
  exit 2
fi

# Ensure namespace exists
if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
  echo "Namespace '$NAMESPACE' not found — creating"
  kubectl create namespace "$NAMESPACE"
fi

# Create or update secret (idempotent)
if [ "$FORCE" -eq 1 ]; then
  echo "--force: deleting existing secret if present"
  kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE" --ignore-not-found
fi

kubectl create secret tls "$SECRET_NAME" --cert="$CERT_PATH" --key="$KEY_PATH" -n "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

echo "Secret '$SECRET_NAME' created/updated in namespace '$NAMESPACE'"

echo "Generated cert: $CERT_PATH"
echo "Generated key:  $KEY_PATH"

echo "Notes:"
echo " - If you used openssl, the certificate is NOT trusted by your system (browser/curl will warn)."
echo " - Prefer mkcert for local trusted certs."

echo "If you plan to commit anything, DO NOT commit the generated cert/key to a public repo. Add '$SCRIPT_DIR/*.pem' to .gitignore."
