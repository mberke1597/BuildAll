FROM python:3.11-slim

WORKDIR /app
COPY apps/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
ENV PYTHONPATH=/app/apps/api:/app/apps/worker

WORKDIR /app/apps/worker
EXPOSE 8001
CMD ["python", "main.py"]
