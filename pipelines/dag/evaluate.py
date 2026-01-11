import pandas as pd
import joblib
from sklearn.metrics import accuracy_score
import mlflow

mlflow.set_tracking_uri("http://mlflow-svc.mlflow.svc.cluster.local:5000")
mlflow.set_experiment("argo-dag-demo")

df = pd.read_csv("/inputs/preprocessed.csv")
X = df.drop("target", axis=1)
y = df["target"]

model = joblib.load("/inputs/model.pkl")
preds = model.predict(X)
acc = accuracy_score(y, preds)

with mlflow.start_run():
    mlflow.log_metric("accuracy", acc)
    mlflow.log_artifact("/inputs/model.pkl", artifact_path="model")

print("Evaluation done.")
