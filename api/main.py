from fastapi import FastAPI, HTTPException
import mlflow.pyfunc
import pandas as pd
import logging

app = FastAPI()

MODEL_URI = "models:/argo-dag-demo/3"  # 後で自動化もできる

# モデルをロード（起動時に1回だけ）。見つからなければアプリは停止させずに503を返す。
try:
    model = mlflow.pyfunc.load_model(MODEL_URI)
except Exception:
    logging.exception("Failed to load model %s", MODEL_URI)
    model = None


@app.post("/predict")
def predict(features: dict):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available")
    df = pd.DataFrame([features])
    pred = model.predict(df)[0]
    return {"prediction": int(pred)}

