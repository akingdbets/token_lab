FROM python:3.12.15-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY tests ./tests

ENTRYPOINT ["python", "/app/src/import_results.py"]
