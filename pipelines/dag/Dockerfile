FROM python:3.10-slim
RUN pip install pandas scikit-learn joblib mlflow boto3
COPY preprocess.py /preprocess.py
COPY train.py /train.py
COPY evaluate.py /evaluate.py

