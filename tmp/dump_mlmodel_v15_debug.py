import json, os, traceback
from mlflow.tracking import MlflowClient
import mlflow

out = {'ok': False, 'steps': []}
try:
    c = MlflowClient(tracking_uri='http://mlflow-svc.mlflow.svc.cluster.local:5000')
    out['steps'].append('connected_mlflow')
    res = c.search_model_versions("name='argo-dag-demo'")
    out['steps'].append(f'found_versions:{len(res)}')
    target = None
    for r in res:
        if str(r.version) == '15':
            target = r
            break
    if target is None:
        out['error'] = 'version 15 not found'
    else:
        out['target'] = {'version': str(target.version), 'source': str(getattr(target,'source',None)), 'run_id': str(getattr(target,'run_id',None))}
        uri = c.get_model_version_download_uri(target.name, target.version)
        out['steps'].append(f'download_uri:{uri}')
        dst = '/tmp/mlmodel_v15_debug'
        try:
            if not os.path.exists(dst):
                os.makedirs(dst)
            local = mlflow.artifacts.download_artifacts(artifact_uri=uri, dst_path=dst)
            out['steps'].append(f'downloaded_to:{local}')
            files = []
            for root, dirs, filenames in os.walk(local):
                for fn in filenames:
                    files.append(os.path.relpath(os.path.join(root, fn), local))
            out['files'] = files
            with open('/tmp/mlmodel_v15_files_debug.json','w') as f:
                f.write(json.dumps({'download_uri':uri, 'local':local, 'files':files}, ensure_ascii=False))
            mlmodel_path = os.path.join(local, 'MLmodel')
            if os.path.exists(mlmodel_path):
                with open(mlmodel_path,'r') as f:
                    content = f.read()
                with open('/tmp/MLmodel_v15.txt','w') as f:
                    f.write(content)
                out['steps'].append('MLmodel_saved')
            else:
                out['steps'].append('MLmodel_missing')
            out['ok'] = True
        except Exception as e:
            out['error_download'] = traceback.format_exc()
except Exception:
    out['error'] = traceback.format_exc()
with open('/tmp/dump_mlmodel_v15_debug.json','w') as f:
    f.write(json.dumps(out, ensure_ascii=False))
print('done')
