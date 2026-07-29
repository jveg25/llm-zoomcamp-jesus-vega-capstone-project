"""Propose document metadata (title, authors, year) from its opening text via the LLM.

The admin reviews and edits these values before ingestion, so the goal is a good
first guess, not perfection. The prompt forbids inventing values: unknown -> blank.
"""
from openai import OpenAI
from pydantic import BaseModel

from common.config import settings
from ingestion.pdf_parser import Page

client = OpenAI(api_key=settings.openai_api_key)

PROMPT = (
    "Extract bibliographic metadata from the document text below.\n"
    "- title: the document's title\n"
    "- authors: comma-separated author names, or \"\" if not stated\n"
    "- year: 4-digit publication year, or null if not stated\n"
    "Do NOT invent values. If a field is not clearly present, leave it empty/null.\n\n"
    "Document text:\n{head}"
)


class DocMetadata(BaseModel):
    title: str
    authors: str
    year: int | None


def extract_metadata(pages: list[Page], fallback_title: str) -> DocMetadata:
    head = "\n".join(p.text for p in pages[:2])[:4000]   # opening ~2 pages is enough
    resp = client.chat.completions.parse(
        model=settings.llm_model,
        messages=[{"role": "user", "content": PROMPT.format(head=head)}],
        response_format=DocMetadata,
    )
    meta = resp.choices[0].message.parsed
    if not meta.title.strip():
        meta.title = fallback_title
    return meta
