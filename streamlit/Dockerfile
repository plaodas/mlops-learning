FROM python:3.10-slim

RUN pip install streamlit mlflow pandas scikit-learn

COPY app.py /app/app.py
WORKDIR /app

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
