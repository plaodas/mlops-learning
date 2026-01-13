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

MODEL_URI = "models:/argo-dag-demo/7"  # 後で自動化もできる

logging.basicConfig(level=logging.INFO)


class _RawModelWrapper:
    def __init__(self, model):
        self._model = model

    def predict(self, df):
        # assume model implements sklearn-like predict
        return self._model.predict(df)


# モデルをロード（起動時に1回だけ）。見つからなければpickleロードのフォールバックを試みる。
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

# Model will be loaded on startup to avoid blocking import time
model = None
# simple in-memory cache for loaded models keyed by models:/... uri or version
model_cache = {}


@app.on_event("startup")
def _startup_load_model():
    global model
    logging.info("Startup: loading model %s", MODEL_URI)
    model = _load_model_with_fallback(MODEL_URI)
    if model is not None:
        model_cache[MODEL_URI] = model
    if model is None:
        logging.error("Model failed to load during startup: %s", MODEL_URI)
    else:
        logging.info("Model loaded successfully")

# 推論エンドポイント
@app.post("/predict")
def predict(features: dict):
    """Predict using the startup-loaded default model."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available")
    df = pd.DataFrame([features])
    pred = model.predict(df)[0]
    return {"prediction": int(pred)}


@app.post("/predict/{version}")
def predict_version(version: str, features: dict):
    """Predict using a specific model version.

    Example: POST /predict/1 with JSON body of features.
    The endpoint will try to load `models:/argo-dag-demo/{version}` and cache it.
    """
    model_uri = f"models:/argo-dag-demo/{version}"

    # try cache first
    m = model_cache.get(model_uri)
    if m is None:
        logging.info("Loading model for uri=%s", model_uri)
        m = _load_model_with_fallback(model_uri)
        if m is None:
            raise HTTPException(status_code=503, detail=f"Model version {version} not available")
        model_cache[model_uri] = m

    df = pd.DataFrame([features])
    pred = model_cache[model_uri].predict(df)[0]
    return {"prediction": int(pred)}


@app.get("/")
def read_root():
    return {"message": "FastAPI is running. Use /predict endpoint to get predictions."}


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}
