FROM python:3.10-slim
# 必要なツールをインストール
# RUN apt-get update && apt-get install -y curl dnsutils && rm -rf /var/lib/apt/lists/*

RUN pip install pandas scikit-learn joblib mlflow boto3 requests
COPY preprocess.py /preprocess.py
COPY train.py /train.py
COPY evaluate.py /evaluate.py

