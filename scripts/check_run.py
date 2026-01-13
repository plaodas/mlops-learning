import os
from mlflow.tracking import MlflowClient
import mlflow
import sys

run_id = sys.argv[1] if len(sys.argv) > 1 else "ec61fb1a03544584815c395a984e4857"
tracking_uri = os.environ.get('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
print('run_id=', run_id, 'tracking_uri=', tracking_uri)
client = MlflowClient(tracking_uri=tracking_uri)
try:
    mlflow.set_tracking_uri(tracking_uri)
    r = client.get_run(run_id)
    print('artifact_uri:', r.info.artifact_uri)
    artifacts = client.list_artifacts(run_id)
    print('artifacts list:', [a.path for a in artifacts])
    if artifacts:
        p = artifacts[0].path
        print('attempt download of', p)
        local = mlflow.artifacts.download_artifacts(artifact_uri=f"runs:/{run_id}/{p}")
        print('downloaded to', local)
    else:
        print('no artifacts found')
except Exception as e:
    print('error querying run:', e)
    sys.exit(2)
