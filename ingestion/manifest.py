"""Read/write data/papers.csv — the reproducible source-of-truth list of papers."""
import csv
from pathlib import Path

MANIFEST = Path("data/papers.csv")
FIELDS = ["filename", "title", "authors", "year", "source_url", "license"]


def load_manifest() -> dict[str, dict]:
    """Map filename -> {title, authors, year, source_url, license}."""
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(newline="") as f:
        return {row["filename"]: row for row in csv.DictReader(f)}


def upsert_row(row: dict) -> None:
    """Insert or replace a paper's manifest row (keyed by filename), keeping the file sorted."""
    rows = load_manifest()
    rows[row["filename"]] = {k: str(row.get(k) or "") for k in FIELDS}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for fname in sorted(rows):
            writer.writerow(rows[fname])
