"""One-off exploration: what does the parser see in each PDF?"""
from pathlib import Path

from ingestion.cleaner import clean_pages
from ingestion.pdf_parser import parse_pdf
from ingestion.chunker import chunk_pages, n_tokens




def dump(pages) -> str:
    return "\n\n".join(f"=== PAGE {p.number} ===\n{p.text}" for p in pages)

if __name__ == "__main__":
    interim = Path("data/interim")
    interim.mkdir(parents=True, exist_ok=True)

    for pdf in sorted(Path("data").glob("*.pdf")):
        meta, pages = parse_pdf(pdf)
        cleaned = clean_pages(pages)

        stem = pdf.stem[:40].replace(" ", "_")
        (interim / f"{stem}.parsed.txt").write_text(dump(pages))
        (interim / f"{stem}.cleaned.txt").write_text(dump(cleaned))

        chunks = chunk_pages(cleaned)
        if chunks:
            sizes = [n_tokens(c.content) for c in chunks]
            print(f"    -> {len(chunks)} chunks | tokens min/avg/max = "
                  f"{min(sizes)}/{sum(sizes)//len(sizes)}/{max(sizes)}")
        else:
            print("    -> 0 chunks  !! investigate")

        print(
            f"{pdf.name[:55]:55} | {meta['page_count']:4} pages "
            f"| kept {len(cleaned)}/{len(pages)} pages | title={meta['title'][:35]!r}"
        )
