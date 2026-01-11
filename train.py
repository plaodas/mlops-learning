import mlflow
import mlflow.sklearn
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import os

# MLflow tracking URI (can be overridden with env var MLFLOW_TRACKING_URI)
# Default to localhost:5000 which matches the service/ingress port
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-svc.mlflow.svc.cluster.local:5000"))
mlflow.set_experiment("argo-demo")

with mlflow.start_run():
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier()
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)

    mlflow.log_metric("accuracy", acc)
    mlflow.sklearn.log_model(model, "model")
