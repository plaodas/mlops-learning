FROM ghcr.io/mlflow/mlflow:latest

# Ensure pip is updated then install boto3 and botocore so MLflow can access S3
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir boto3 botocore

RUN apt-get update && apt-get install -y curl unzip && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws
