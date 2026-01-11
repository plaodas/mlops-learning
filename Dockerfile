FROM python:3.10-slim
RUN pip install mlflow scikit-learn
COPY train.py /train.py
CMD ["python", "/train.py"]
