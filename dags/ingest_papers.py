"""Airflow DAG: download manifest papers, then ingest any not yet in the knowledge base.

Two tasks (download -> ingest) wrapping the same ingestion code the CLI and admin
upload use. Idempotent: already-ingested papers are skipped before any embedding.
Imports are inside the tasks so the DAG file parses even without the project deps.
"""
import os
from datetime import datetime

from airflow.decorators import dag, task

PROJECT_DIR = "/opt/airflow/project"


@dag(schedule="@daily", start_date=datetime(2026, 1, 1), catchup=False,
     tags=["ingestion"], doc_md=__doc__)
def ingest_papers():

    @task
    def download() -> None:
        os.chdir(PROJECT_DIR)                     # ingestion code uses relative data/ paths
        from ingestion.downloader import download_missing
        download_missing()

    @task
    def ingest() -> None:
        os.chdir(PROJECT_DIR)
        from pathlib import Path
        from ingestion.manifest import load_manifest
        from ingestion.run import ingest_file
        for filename, row in load_manifest().items():
            path = Path("data") / filename
            if not path.exists():
                print(f"MISS {filename}: not present")
                continue
            year = int(row["year"]) if (row.get("year") or "").strip() else None
            ingest_file(path, title=(row.get("title") or "").strip() or None,
                        authors=(row.get("authors") or "").strip() or None,
                        year=year, source_url=(row.get("source_url") or "").strip() or None)

    download() >> ingest()


ingest_papers()
