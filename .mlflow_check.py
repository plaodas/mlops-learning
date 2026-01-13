from mlflow.tracking import MlflowClient
c = MlflowClient()
print("registered models:")
try:
    rms = c.search_registered_models()
    for rm in rms:
        print(rm.name)
except Exception as e:
    print("search_registered_models error:", e)
print("\nlatest versions for argo-dag-demo:")
try:
    v = c.get_latest_versions("argo-dag-demo")
    for mv in v:
        print(mv.version, mv.current_stage, mv.source)
except Exception as e:
    print("get_latest_versions error:", e)
run='113503b7a4784528964d9157fa0b0385'
print("\ncheck run", run)
try:
    r = c.get_run(run)
    print('artifact_uri:', r.info.artifact_uri)
except Exception as e:
    print('get_run error:', e)
