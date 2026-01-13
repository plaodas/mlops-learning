import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
import mlflow
import mlflow.sklearn


# Respect the tracking URI injected by the Argo task
mlflow_tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
if mlflow_tracking_uri:
    mlflow.set_tracking_uri(mlflow_tracking_uri)

df = pd.read_csv("/inputs/preprocessed.csv")
X = df.drop("target", axis=1)
y = df["target"]

model = RandomForestClassifier()
model.fit(X, y)

# Log the model as an MLflow model under artifact path "model"
with mlflow.start_run() as run:
    mlflow.sklearn.log_model(model, artifact_path="model")
    # Register model version so registry holds an externally-accessible source
    run_id = run.info.run_id
    # model_uri = f"runs:/{run_id}/model"
    artifact_uri = mlflow.get_artifact_uri("model")

    from mlflow.tracking import MlflowClient
    client = MlflowClient()
    try:
        client.create_model_version(name="argo-dag-demo", source=artifact_uri, run_id=run_id)
        print(f"Requested registration for model argo-dag-demo from {artifact_uri}")
    except Exception as e:
        print('Model registration request failed:', e)

# Also save a raw pickle for convenience
joblib.dump(model, "/outputs/model.pkl")
print("Training and MLflow logging done.")
