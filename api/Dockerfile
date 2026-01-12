FROM python:3.10-slim

RUN pip install fastapi uvicorn mlflow pandas scikit-learn

COPY main.py /app/main.py
WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

