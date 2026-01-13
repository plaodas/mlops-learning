FROM python:3.10-slim

RUN pip install fastapi uvicorn mlflow pandas scikit-learn boto3

COPY main.py /app/main.py
WORKDIR /app

# Run the FastAPI app with Uvicorn Log level set to debug
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
