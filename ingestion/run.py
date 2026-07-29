"""Ingest PDFs into the knowledge base: parse -> clean -> chunk -> embed -> load."""
import sys
from pathlib import Path

from ingestion.chunker import chunk_pages
from ingestion.cleaner import clean_pages
from ingestion.embedder import embed_texts
from ingestion.loader import load_paper
from ingestion.pdf_parser import parse_pdf


JUNK_TITLES = {"about:blank", "paper title", "untitled", "microsoft word"}

def ingest_pdf(path: Path) -> None:
    meta, pages = parse_pdf(path)
    chunks = chunk_pages(clean_pages(pages))
    if not chunks:
        print(f"SKIP {path.name}: produced no chunks")
        return
    embeddings = embed_texts([c.content for c in chunks])

    title = (meta["title"] or "").strip()
    if not title or title.lower() in JUNK_TITLES:   # empty OR junk -> use the filename
        title = path.stem

    paper_id = load_paper(path.name, title, chunks, embeddings)   # now saves the good title
    if paper_id is None:
        print(f"SKIP {path.name}: already ingested")
    else:
        print(f"OK   {path.name}: paper_id={paper_id}, {len(chunks)} chunks")


if __name__ == "__main__":
    pdfs = [Path(a) for a in sys.argv[1:]] or sorted(Path("data").glob("*.pdf"))
    for pdf in pdfs:
        ingest_pdf(pdf)