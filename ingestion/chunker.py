import re
from dataclasses import dataclass

import tiktoken

from ingestion.pdf_parser import Page

# Matches numbered ('2.', '4.1') and roman ('II.', 'IV.') headings followed by a short title
HEADING_RE = re.compile(r"^\s*(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVXLC]+\.)\s+[A-Z][^\n]{3,80}$")

ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    index: int
    section: str | None
    page_start: int
    page_end: int
    content: str


def n_tokens(text: str) -> int:
    return len(ENC.encode(text))


def chunk_pages(
    pages: list[Page],
    target_tokens: int = 800,
    overlap_tokens: int = 100,
    min_tokens: int = 30,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    section: str | None = None
    buf: list[tuple[int, str]] = []          # (page_number, line)
    buf_tokens = 0

    def flush(keep_overlap: bool) -> None:
        nonlocal buf, buf_tokens
        content = "\n".join(line for _, line in buf).strip()
        if content and n_tokens(content) >= min_tokens:   # drop tiny fragments
            chunks.append(Chunk(len(chunks), section, buf[0][0], buf[-1][0], content))
        if keep_overlap and buf:
            tail, total = [], 0
            for pg, line in reversed(buf):                # walk back until ~overlap_tokens
                tail.insert(0, (pg, line))
                total += n_tokens(line)
                if total >= overlap_tokens:
                    break
            buf, buf_tokens = tail, total
        else:
            buf, buf_tokens = [], 0

    for page in pages:
        for line in page.text.splitlines():
            if not line.strip():
                continue
            if HEADING_RE.match(line.strip()):
                flush(keep_overlap=False)     # hard boundary: no overlap across sections
                section = line.strip()
                continue
            buf.append((page.number, line))
            buf_tokens += n_tokens(line)
            if buf_tokens >= target_tokens:
                flush(keep_overlap=True)      # soft boundary: overlap preserves continuity

    flush(keep_overlap=False)                 # whatever remains at the end
    return chunks