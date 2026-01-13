FROM ghcr.io/mlflow/mlflow:latest

# Ensure pip is updated then install boto3 and botocore so MLflow can access S3
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir boto3 botocore
