FROM python:3.11-slim

RUN pip install --no-cache-dir --timeout 180 --retries 15 mlflow==3.16.0

EXPOSE 5000

CMD ["mlflow", "server", \
     "--host", "0.0.0.0", "--port", "5000", \
     "--backend-store-uri", "sqlite:////mlflow-data/mlflow.db", \
     "--serve-artifacts", \
     "--artifacts-destination", "/mlflow-data/mlartifacts", \
     "--allowed-hosts", "mlflow:*,localhost:*,localhost,127.0.0.1:*,127.0.0.1"]
