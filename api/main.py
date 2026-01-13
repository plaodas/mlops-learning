from fastapi import FastAPI, HTTPException
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
import mlflow
import pandas as pd
import logging
import tempfile
import os
import joblib

app = FastAPI()

MODEL_URI = "models:/argo-dag-demo/3"  # 後で自動化もできる


class _RawModelWrapper:
    def __init__(self, model):
        self._model = model

    def predict(self, df):
        # assume model implements sklearn-like predict
        return self._model.predict(df)


# モデルをロード（起動時に1回だけ）。見つからなければアプリは停止させずに503を返す。
def _load_model_with_fallback(model_uri: str):
    try:
        return mlflow.pyfunc.load_model(model_uri)
    except Exception:
        logging.exception("pyfunc.load_model failed for %s", model_uri)

    # Fallback: try to resolve model version -> runs:/... and download artifact
    try:
        # models:/<name>/<version>
        if model_uri.startswith("models:/"):
            parts = model_uri[len("models:/"):].split("/")
            if len(parts) >= 2:
                name, version = parts[0], parts[1]
                client = MlflowClient()
                artifact_uri = client.get_model_version_download_uri(name, version)
                # download artifact to tmp dir
                dst = tempfile.mkdtemp(prefix="mlflow_art_")
                local_path = mlflow.artifacts.download_artifacts(artifact_uri=artifact_uri, dst_path=dst)

                # If MLmodel exists, load via pyfunc from that local path
                mlmodel_path = os.path.join(local_path, "MLmodel")
                if os.path.exists(mlmodel_path):
                    return mlflow.pyfunc.load_model(local_path)

                # Otherwise, look for common model files (model.pkl / model.joblib)
                for root, dirs, files in os.walk(local_path):
                    for fn in files:
                        if fn.endswith(".pkl") or fn.endswith(".joblib"):
                            full = os.path.join(root, fn)
                            try:
                                raw = joblib.load(full)
                                return _RawModelWrapper(raw)
                            except Exception:
                                logging.exception("Failed to joblib.load %s", full)
    except Exception:
        logging.exception("Fallback loader failed for %s", model_uri)

    return None


model = _load_model_with_fallback(MODEL_URI)


@app.post("/predict")
def predict(features: dict):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available")
    df = pd.DataFrame([features])
    pred = model.predict(df)[0]
    return {"prediction": int(pred)}

