from mlflow.tracking import MlflowClient
import mlflow, traceback
client = MlflowClient(tracking_uri='http://mlflow-svc.mlflow.svc.cluster.local:5000')
try:
    res = client.search_model_versions("name='argo-dag-demo'")
    print('SEARCH_RESULT_COUNT', len(res))
    for r in sorted(res, key=lambda v: int(v.version)):
        print('MODEL_VERSION', r.version)
        print('SOURCE', r.source)
        print('RUN_ID', getattr(r, 'run_id', None))
        print('STATUS', getattr(r, 'status', None))
        print('---')
    if res:
        latest = max(int(v.version) for v in res)
        print('LATEST_VERSION', latest)
        uri = f"models:/argo-dag-demo/{latest}"
        print('ATTEMPT_LOAD_URI', uri)
        try:
            m = mlflow.pyfunc.load_model(uri)
            print('LOAD_OK')
        except Exception:
            print('LOAD_EXCEPTION')
            traceback.print_exc()
    else:
        print('NO_VERSIONS')
except Exception:
    traceback.print_exc()
