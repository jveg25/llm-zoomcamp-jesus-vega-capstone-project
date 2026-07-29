"""Parse any supported document into (metadata, pages). Dispatches on file extension.

PDFs go through the layout-aware PyMuPDF parser; text formats (txt/md/csv/…) are
read as a single page. Everything downstream (clean -> chunk -> embed) is unchanged.
"""
from pathlib import Path

from ingestion.pdf_parser import Page, parse_pdf

TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json"}


def parse_file(path: Path) -> tuple[dict, list[Page]]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    if ext in TEXT_EXTS:
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = {"title": "", "author": "", "page_count": 1}
        return meta, [Page(number=1, text=text)]
    raise ValueError(f"Unsupported file type: {ext!r} (supported: .pdf, {', '.join(sorted(TEXT_EXTS))})")
