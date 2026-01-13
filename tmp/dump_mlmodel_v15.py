from mlflow.tracking import MlflowClient
import mlflow, os
import json
c = MlflowClient(tracking_uri='http://mlflow-svc.mlflow.svc.cluster.local:5000')
res = c.search_model_versions("name='argo-dag-demo'")
for r in res:
    if str(r.version)=='15':
        uri = c.get_model_version_download_uri(r.name, r.version)
        outdir = '/tmp/mlmodel_v15'
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        local = mlflow.artifacts.download_artifacts(artifact_uri=uri, dst_path=outdir)
        mlmodel_path = os.path.join(local, 'MLmodel')
        files = []
        for root, dirs, filenames in os.walk(local):
            for fn in filenames:
                files.append(os.path.relpath(os.path.join(root, fn), local))
        with open('/tmp/mlmodel_v15_files.json','w') as f:
            f.write(json.dumps({'download_uri':uri, 'local':local, 'files':files}, ensure_ascii=False))
        if os.path.exists(mlmodel_path):
            with open(mlmodel_path,'r') as f:
                content = f.read()
            with open('/tmp/MLmodel_v15.txt','w') as f:
                f.write(content)
        break
print('done')
