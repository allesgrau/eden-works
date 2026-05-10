FROM python:3.11-slim
RUN pip install --no-cache-dir psycopg2-binary requests
WORKDIR /app
COPY snapshot_writer.py .
ENV PYTHONUNBUFFERED=1
CMD ["python3", "snapshot_writer.py"]
