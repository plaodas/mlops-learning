import os
import streamlit as st
import mlflow.pyfunc
import pandas as pd
import s3_utils

st.title("Iris 推論ダッシュボード")

# MLflow model URI (registry) — keep as fallback
MODEL_URI = "models:/argo-dag-demo/1"  # 後で調整可能


@st.cache_resource
def load_registry_model():
    return mlflow.pyfunc.load_model(MODEL_URI)


# session stored model (can be registry model or artifact-loaded model)
if "model" not in st.session_state:
    st.session_state["model"] = None

# Provide an explicit action to load model from MLflow Model Registry
if st.button("Load registry model"):
    try:
        with st.spinner("Loading model from MLflow Model Registry..."):
            st.session_state["model"] = load_registry_model()
        st.success(f"Loaded registry model: {MODEL_URI}")
    except Exception as e:
        # keep session model as-is (likely None) and show helpful error
        st.session_state["model"] = st.session_state.get("model")
        st.error(f"Failed to load registry model: {e}")


st.subheader("モデルをロード")

default_artifact = (
    "artifact:s3:minio.argo.svc.cluster.local:9000:argo-artifacts:mlflow-dag/"
    "mlflow-dag-train-2621001753/model.tgz"
)

artifact_uri = st.text_input("Artifact URI (S3/MinIO)", value=default_artifact)

if st.button("Download & Load artifact"):
    try:
        with st.spinner("Downloading artifact and loading model..."):
            local_path = s3_utils.download_and_extract_model(
                artifact_uri,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            )
            model = s3_utils.load_model_from_path(local_path)
            st.session_state["model"] = model
            st.success(f"Loaded model from {artifact_uri}")
    except Exception as e:
        st.error(f"Failed to download/load model: {e}")


st.subheader("特徴量を入力してください")

sepal_length = st.number_input("sepal length (cm)", 0.0, 10.0, 5.1)
sepal_width = st.number_input("sepal width (cm)", 0.0, 10.0, 3.5)
petal_length = st.number_input("petal length (cm)", 0.0, 10.0, 1.4)
petal_width = st.number_input("petal width (cm)", 0.0, 10.0, 0.2)

if st.button("推論する"):
    if st.session_state.get("model") is None:
        st.error("モデルがロードされていません。右上の 'Download & Load artifact' かレジストリモデルを確認してください。")
    else:
        df = pd.DataFrame([[
            sepal_length, sepal_width, petal_length, petal_width
        ]], columns=["sepal length (cm)", "sepal width (cm)", "petal length (cm)", "petal width (cm)"])

        pred = st.session_state["model"].predict(df)[0]
        st.success(f"予測クラス: {pred}")

