from mlflow.tracking import MlflowClient
import json
c = MlflowClient(tracking_uri='http://mlflow-svc.mlflow.svc.cluster.local:5000')
res = c.search_model_versions("name='argo-dag-demo'")
out = None
for r in res:
    if str(r.version) == '15':
        out = {
            'version': str(r.version),
            'current_stage': str(getattr(r, 'current_stage', None)),
            'source': str(getattr(r, 'source', None)),
            'run_id': str(getattr(r, 'run_id', None)),
            'status': str(getattr(r, 'status', None))
        }
        break
print(json.dumps(out, ensure_ascii=False))
