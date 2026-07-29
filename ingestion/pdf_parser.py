from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class Page:
    number: int          # 1-based, matches what a human sees in a PDF viewer
    text: str


def parse_pdf(path: Path) -> tuple[dict, list[Page]]:
    """Extract document metadata and per-page text from a PDF."""
    doc = fitz.open(path)
    meta = {
        "title": (doc.metadata or {}).get("title") or "",
        "author": (doc.metadata or {}).get("author") or "",
        "page_count": doc.page_count,
    }
    pages = [
        Page(number=i + 1, text=page.get_text("text"))
        for i, page in enumerate(doc)
    ]
    doc.close()
    return meta, pages