#!/usr/bin/env python3
"""Smoke test: download MLflow artifact from S3/MinIO, load model, run one prediction.

Usage:
  python streamlit/test_load_model.py [ARTIFACT_URI]

This script loads `streamlit/s3_utils.py` by path to avoid import-name collision with
the external `streamlit` package.
"""
import sys
import os
import logging
from pathlib import Path
import pandas as pd
import mlflow.pyfunc
import importlib.util

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_local_s3_utils():
    repo_root = Path(__file__).resolve().parents[1]
    s3_utils_path = repo_root / "streamlit" / "s3_utils.py"
    if not s3_utils_path.exists():
        raise FileNotFoundError(f"s3_utils not found at {s3_utils_path}")
    spec = importlib.util.spec_from_file_location("local_s3_utils", str(s3_utils_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    artifact_default = (
        "artifact:s3:minio.argo.svc.cluster.local:9000:argo-artifacts:"
        "mlflow-dag/mlflow-dag-train-2621001753/model.tgz"
    )
    artifact_uri = sys.argv[1] if len(sys.argv) > 1 else artifact_default

    aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")

    logger.info("Using artifact URI: %s", artifact_uri)

    s3_utils = load_local_s3_utils()

    try:
        local_path = s3_utils.download_and_extract_model(artifact_uri, aws_key, aws_secret)
        logger.info("Model extracted to %s", local_path)

        # try MLflow loader first, otherwise fallback to raw pickle/joblib
        try:
            # import local s3_utils to use its loader
            s3_utils = load_local_s3_utils()
            model = s3_utils.load_model_from_path(local_path)
        except Exception:
            logger.exception("Failed to load via s3_utils.load_model_from_path, trying mlflow directly")
            model = mlflow.pyfunc.load_model(local_path)
        logger.info("Model loaded OK")

        # create a sample iris input (same columns used in the app)
        df = pd.DataFrame([
            [5.1, 3.5, 1.4, 0.2]
        ], columns=["sepal length (cm)", "sepal width (cm)", "petal length (cm)", "petal width (cm)"])

        pred = model.predict(df)
        print("Prediction:", pred)
    except Exception as e:
        logger.exception("Test failed: %s", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
