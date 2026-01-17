import pandas as pd
import joblib
from sklearn.metrics import accuracy_score, log_loss
import mlflow
from mlflow.tracking import MlflowClient

mlflow.set_tracking_uri("http://mlflow-svc.mlflow.svc.cluster.local:5000")
EXPERIMENT_NAME = "argo-dag-demo"

# Ensure the experiment exists and is not deleted. If it's deleted, restore it so
# `mlflow.set_experiment` can succeed when run inside the pipeline environment.
client = MlflowClient()
exp = client.get_experiment_by_name(EXPERIMENT_NAME)
if exp is not None and exp.lifecycle_stage == "deleted":
    client.restore_experiment(exp.experiment_id)

mlflow.set_experiment(EXPERIMENT_NAME)

df = pd.read_csv("/inputs/preprocessed.csv")
X = df.drop("target", axis=1)
y = df["target"]

model = joblib.load("/inputs/model.pkl")
preds = model.predict(X)
acc = accuracy_score(y, preds)

# Replace model.predict with model.predict_proba to calculate log_loss correctly
probs = model.predict_proba(X)  # クラス確率を取得
loss = log_loss(y, probs)  # クラス確率を使用して log_loss を計算

with mlflow.start_run() as run:
    mlflow.log_metric("accuracy", acc)
    mlflow.log_metric("loss", loss)
    # Save model in MLflow format so an MLmodel metadata file is created
    try:
        import mlflow.sklearn
        mlflow.sklearn.log_model(model, artifact_path="model")

    except Exception:
        # If structured logging fails, fall back to raw artifact upload to avoid breaking pipeline
        mlflow.log_artifact("/inputs/model.pkl", artifact_path="model")

    client = MlflowClient()
    # model_uri = f"runs:/{run.info.run_id}/model"
    # Get the REAL artifact URI (S3/MinIO path)
    artifact_uri = mlflow.get_artifact_uri("model")

    # Create the registered model if it doesn't exist. If it already exists,
    # try to restore it (if deleted) or ignore the error so the pipeline can
    # continue to create a new model version.
    try:
        client.create_registered_model(EXPERIMENT_NAME)
    except Exception as e:
        err = str(e)
        # If the registered model already exists, ignore and continue.
        # MLflow's client may not provide a restore API for registered models,
        # so attempting to call a non-existent method would raise an AttributeError.
        if "RESOURCE_ALREADY_EXISTS" in err:
            pass
        else:
            raise

    client.create_model_version(
        name=EXPERIMENT_NAME,
        source=artifact_uri,
        run_id=run.info.run_id
    )


print(f"Accuracy: {acc}, Loss: {loss}")

with open("/outputs/accuracy", "w") as f:
    f.write(str(acc))

with open("/outputs/loss", "w") as f:
    f.write(str(loss))

print("Evaluation done.")
