import pkgutil, mlflow, traceback, sys
print('mlflow', mlflow.__version__)
print('boto3_installed', pkgutil.find_loader('boto3') is not None)
try:
    m = mlflow.pyfunc.load_model('models:/argo-dag-demo/1')
    print('loaded', type(m))
except Exception:
    traceback.print_exc()
    sys.exit(1)
print('done')
