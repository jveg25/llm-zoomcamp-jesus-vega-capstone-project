"""Ingest a document into the knowledge base: parse -> clean -> chunk -> embed -> load.

`ingest_file` is the reusable core, called by the CLI, the Airflow DAG, and the
admin upload endpoint. Metadata (title/authors/year/source_url) may be passed in
(e.g. reviewed by an admin); otherwise it falls back to the parser / filename.
"""
import sys
from pathlib import Path

from ingestion.chunker import chunk_pages
from ingestion.cleaner import clean_pages
from ingestion.embedder import embed_texts
from ingestion.loader import load_paper, paper_exists
from ingestion.manifest import load_manifest
from ingestion.parser import parse_file

JUNK_TITLES = {"about:blank", "paper title", "untitled", "microsoft word"}


def ingest_file(
    path: Path,
    title: str | None = None,
    authors: str | None = None,
    year: int | None = None,
    source_url: str | None = None,
) -> int | None:
    """Ingest one document. Returns paper_id, or None if it produced no chunks
    or was already ingested (idempotent by filename)."""
    if paper_exists(path.name):                          # check before parsing/embedding
        print(f"SKIP {path.name}: already ingested")
        return None
    meta, pages = parse_file(path)
    chunks = chunk_pages(clean_pages(pages))
    if not chunks:
        print(f"SKIP {path.name}: produced no chunks")
        return None
    embeddings = embed_texts([c.content for c in chunks])

    if not title:
        title = (meta.get("title") or "").strip()
        if not title or title.lower() in JUNK_TITLES:   # empty OR junk -> filename
            title = path.stem

    paper_id = load_paper(path.name, title, chunks, embeddings, authors, year, source_url)
    print(f"{'SKIP' if paper_id is None else 'OK  '} {path.name}: "
          f"{'already ingested' if paper_id is None else f'paper_id={paper_id}, {len(chunks)} chunks'}")
    return paper_id


if __name__ == "__main__":
    manifest = load_manifest()
    paths = [Path(a) for a in sys.argv[1:]] or sorted(Path("data").glob("*.pdf"))
    for path in paths:
        row = manifest.get(path.name, {})
        year = int(row["year"]) if (row.get("year") or "").strip() else None
        ingest_file(
            path,
            title=(row.get("title") or "").strip() or None,
            authors=(row.get("authors") or "").strip() or None,
            year=year,
            source_url=(row.get("source_url") or "").strip() or None,
        )
