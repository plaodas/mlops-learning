FROM python:3.10-slim

WORKDIR /app

# Install Python dependencies from requirements.txt (copied before other files for caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY s3_utils.py /app/s3_utils.py

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
