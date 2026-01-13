#!/bin/sh
# Smoke test: run predict on target version inside fastapi pod and fetch MLmodel from mlflow pod
NS=${1:-mlflow}
VERSION=${2:-15}
FASTAPI_POD=$(kubectl -n $NS get pods -l app=fastapi -o jsonpath='{.items[0].metadata.name}')
MLFLOW_POD=$(kubectl -n $NS get pods -l app=mlflow -o jsonpath='{.items[0].metadata.name}')
set -e
kubectl -n $NS cp scripts/smoke_predict.py $FASTAPI_POD:/tmp/smoke_predict.py
kubectl -n $NS exec $FASTAPI_POD -- python3 /tmp/smoke_predict.py $VERSION > /tmp/smoke_predict_result.json || true
kubectl -n $NS cp $FASTAPI_POD:/tmp/smoke_predict_result.json .
kubectl -n $NS cp tmp/dump_mlmodel_v15.py $MLFLOW_POD:/tmp/dump_mlmodel_v15.py
kubectl -n $NS exec $MLFLOW_POD -- python3 /tmp/dump_mlmodel_v15.py || true
kubectl -n $NS cp $MLFLOW_POD:/tmp/MLmodel_v15.txt . || true
kubectl -n $NS cp $MLFLOW_POD:/tmp/mlmodel_v15_files.json . || true
kubectl -n $NS logs $FASTAPI_POD --since=5m > fastapi_recent.log || true
kubectl -n $NS logs $MLFLOW_POD --since=5m > mlflow_recent.log || true

echo "Artifacts copied to working dir: smoke_predict_result.json, MLmodel_v15.txt, mlmodel_v15_files.json, fastapi_recent.log, mlflow_recent.log"
