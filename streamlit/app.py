import streamlit as st
import mlflow.pyfunc
import pandas as pd

st.title("Iris 推論ダッシュボード")

# MLflow model URI
MODEL_URI = "models:/argo-dag-demo/1"  # 後で調整可能

@st.cache_resource
def load_model():
    return mlflow.pyfunc.load_model(MODEL_URI)

model = load_model()

st.subheader("特徴量を入力してください")

sepal_length = st.number_input("sepal length (cm)", 0.0, 10.0, 5.1)
sepal_width = st.number_input("sepal width (cm)", 0.0, 10.0, 3.5)
petal_length = st.number_input("petal length (cm)", 0.0, 10.0, 1.4)
petal_width = st.number_input("petal width (cm)", 0.0, 10.0, 0.2)

if st.button("推論する"):
    df = pd.DataFrame([[
        sepal_length, sepal_width, petal_length, petal_width
    ]], columns=["sepal length (cm)", "sepal width (cm)", "petal length (cm)", "petal width (cm)"])

    pred = model.predict(df)[0]
    st.success(f"予測クラス: {pred}")

