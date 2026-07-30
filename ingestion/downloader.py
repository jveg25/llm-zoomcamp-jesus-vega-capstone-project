"""Download any manifest PDF not already in data/. Idempotent: skips files present."""
from pathlib import Path

import requests

from ingestion.manifest import load_manifest

DATA_DIR = Path("data")


def download_missing() -> None:
    for filename, row in load_manifest().items():
        dest = DATA_DIR / filename
        if dest.exists():
            print(f"HAVE {filename}")
            continue
        url = (row.get("source_url") or "").strip()
        if not url:
            print(f"MISS {filename}: absent and no source_url — add the file to data/ manually")
            continue
        print(f"GET  {filename} <- {url}")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)


if __name__ == "__main__":
    download_missing()
