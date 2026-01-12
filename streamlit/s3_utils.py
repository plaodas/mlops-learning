import os
import tempfile
import tarfile
import boto3
import logging
from typing import Optional
import mlflow.pyfunc
import pickle
import joblib

logger = logging.getLogger(__name__)


def parse_artifact_uri(uri: str):
    """Parse artifact URI produced by Argo/MLflow examples.

    Supported forms:
    - artifact:s3:<host>:<port>:<bucket>:<path/to/object>
    - s3://<bucket>/<path/to/object>
    Returns dict with keys: endpoint_url (optional), bucket, key
    """
    if uri.startswith("artifact:s3:"):
        # split into 6 parts max so the key can contain colons if any
        parts = uri.split(":", 5)
        # parts -> ["artifact","s3","host","port","bucket","key"]
        if len(parts) < 6:
            raise ValueError(f"Invalid artifact:s3 URI: {uri}")
        host = parts[2]
        port = parts[3]
        bucket = parts[4]
        key = parts[5]
        endpoint_url = f"http://{host}:{port}"
        return {"endpoint_url": endpoint_url, "bucket": bucket, "key": key}
    elif uri.startswith("s3://"):
        # s3://bucket/path/to/object
        without = uri[len("s3://") :]
        bucket, _, key = without.partition("/")
        return {"endpoint_url": None, "bucket": bucket, "key": key}
    else:
        raise ValueError(f"Unsupported artifact URI format: {uri}")


def download_and_extract_model(artifact_uri: str,
                               aws_access_key_id: Optional[str] = None,
                               aws_secret_access_key: Optional[str] = None) -> str:
    """Download model artifact (tar.gz) from S3/MinIO and extract to a temp dir.

    Returns path to the extracted model directory (first top-level dir if present, else the temp dir).
    """
    info = parse_artifact_uri(artifact_uri)
    endpoint_url = info.get("endpoint_url")
    bucket = info["bucket"]
    key = info["key"]

    session_kwargs = {}
    if aws_access_key_id is not None:
        session_kwargs["aws_access_key_id"] = aws_access_key_id
    if aws_secret_access_key is not None:
        session_kwargs["aws_secret_access_key"] = aws_secret_access_key

    session = boto3.session.Session(**session_kwargs)
    client_kwargs = {}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    s3 = session.client("s3", **client_kwargs)

    tmpdir = tempfile.mkdtemp(prefix="mlflow_artifact_")
    tar_path = os.path.join(tmpdir, "model.tgz")

    logger.info("Downloading s3://%s/%s to %s", bucket, key, tar_path)
    with open(tar_path, "wb") as f:
        s3.download_fileobj(bucket, key, f)

    # try to extract
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=tmpdir)
    except tarfile.ReadError:
        # not a tar.gz; if it's a raw folder or model file, just return path
        logger.warning("Downloaded file is not a tar.gz archive: %s", tar_path)

    # find top-level extracted directory (ignore the tar file)
    entries = [e for e in os.listdir(tmpdir) if e != os.path.basename(tar_path)]
    if len(entries) == 1 and os.path.isdir(os.path.join(tmpdir, entries[0])):
        return os.path.join(tmpdir, entries[0])
    return tmpdir


def load_model_from_path(path: str):
    """Load a model from an extracted artifact path.

    Tries MLflow format first (MLmodel present). If not found, tries common
    single-file formats like `model.pkl` or `model.joblib` and returns an object
    exposing a `predict()` method.
    """
    mlmodel_file = os.path.join(path, "MLmodel")
    if os.path.exists(mlmodel_file):
        return mlflow.pyfunc.load_model(path)

    # fallback: look for single-file model pickles
    candidates = [
        "model.pkl",
        "model.joblib",
        "model.pkl.gz",
        "model.joblib.gz",
    ]
    for c in candidates:
        p = os.path.join(path, c)
        if os.path.exists(p):
            # try joblib first for .joblib/.pkl
            try:
                return joblib.load(p)
            except Exception:
                with open(p, "rb") as f:
                    return pickle.load(f)

    # last resort: if path itself is a .pkl
    if path.endswith(".pkl") or path.endswith(".joblib"):
        try:
            return joblib.load(path)
        except Exception:
            with open(path, "rb") as f:
                return pickle.load(f)

    raise FileNotFoundError(f"No MLflow model or supported model file found in {path}")
