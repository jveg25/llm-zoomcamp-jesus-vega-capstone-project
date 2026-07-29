import re
from collections import Counter

from ingestion.pdf_parser import Page

REFS_RE = re.compile(r"^\s*(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)

# One-off journal boilerplate on the first page(s) — never repeated, so the
# frequency-based filter can't catch it
FRONT_MATTER_RE = re.compile(
    r"^\s*(academic editors?|received:|revised:|accepted:|published:|citation:|"
    r"copyright:|licensee mdpi|creative commons|this article is an open access|"
    r"https?://creativecommons|doi\.org|correspondence:)", re.IGNORECASE)



def _line_key(line: str) -> str:
    """Normalize a line so 'page 45' and 'page 46' compare as identical."""
    return re.sub(r"\d+", "#", line.strip().lower())


def remove_repeated_lines(pages: list[Page], threshold: float = 0.4) -> list[Page]:
    """Drop lines appearing on >= threshold of pages: headers, footers, page numbers."""
    if len(pages) < 3:
        return pages
    counts: Counter = Counter()
    for page in pages:
        counts.update({_line_key(l) for l in page.text.splitlines() if l.strip()})
    junk = {
        key for key, c in counts.items()
        if c / len(pages) >= threshold and len(key) < 200   # short lines only: never nuke real prose
    }
    return [
        Page(p.number, "\n".join(l for l in p.text.splitlines() if _line_key(l) not in junk))
        for p in pages
    ]


def fix_hyphenation(text: str) -> str:
    """Rejoin words split across lines: 'lith-\\nium' -> 'lithium'."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)



def remove_front_matter(pages: list[Page], first_n: int = 2) -> list[Page]:
    """Drop boilerplate lines from the first pages (title/authors survive: no colon-keywords)."""
    return [
        p if i >= first_n else
        Page(p.number, "\n".join(l for l in p.text.splitlines()
                                 if not FRONT_MATTER_RE.match(l)))
        for i, p in enumerate(pages)
    ]

def clean_pages(pages: list[Page]) -> list[Page]:
    pages = remove_front_matter(pages)
    pages = remove_repeated_lines(pages)
    out: list[Page] = []
    for i, p in enumerate(pages):
        text = p.text
        m = REFS_RE.search(text)
        if m and i / len(pages) > 0.5:      # only trust a References heading in the back half
            out.append(Page(p.number, fix_hyphenation(text[: m.start()])))
            break                            # drop this page's tail and all following pages
        out.append(Page(p.number, fix_hyphenation(text)))
    return out