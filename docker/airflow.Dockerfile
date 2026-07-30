# Airflow + the project's ingestion dependencies (the base image has neither).
FROM apache/airflow:2.10.4

RUN pip install --no-cache-dir \
    "openai>=2.44" \
    "pgvector>=0.5" \
    "psycopg[binary]>=3.3" \
    "pydantic-settings>=2.14" \
    "pymupdf>=1.28" \
    "tiktoken>=0.13" \
    "requests>=2.31"
