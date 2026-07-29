"""Generate a ground-truth dataset: questions whose source chunk is known."""
import csv
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel

from common.config import settings
from common.db import get_connection

client = OpenAI(api_key=settings.openai_api_key)
OUT = Path("evaluation/ground_truth.csv")

PROMPT = """You are a student learning about battery energy storage systems.
Based ONLY on the following passage, write 2 questions that this passage answers.
The questions must make sense on their own (no "this passage", no "the study").
Vary the style: one specific/technical, one broader.

Passage from "{title}", section "{section}":
{content}"""


class Questions(BaseModel):
    questions: list[str]


def fetch_chunks() -> list[tuple]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.id, c.paper_id, p.title, c.section, c.content
            FROM chunks c JOIN papers p ON p.id = c.paper_id
            WHERE length(c.content) > 300      -- skip fragments: no meaningful questions in them
            ORDER BY c.id
        """)
        return cur.fetchall()


def main() -> None:
    done = set()
    if OUT.exists():                            # resumable: skip chunks already processed
        with OUT.open() as f:
            done = {int(row["chunk_id"]) for row in csv.DictReader(f)}

    chunks = fetch_chunks()
    with OUT.open("a", newline="") as f:
        writer = csv.writer(f)
        if not done:
            writer.writerow(["question", "chunk_id", "paper_id"])
        for i, (chunk_id, paper_id, title, section, content) in enumerate(chunks):
            if chunk_id in done:
                continue
            resp = client.chat.completions.parse(
                model=settings.llm_model,
                messages=[{"role": "user", "content": PROMPT.format(
                    title=title, section=section or "n/a", content=content)}],
                response_format=Questions,
            )
            for q in resp.choices[0].message.parsed.questions:
                writer.writerow([q, chunk_id, paper_id])
            f.flush()
            print(f"{i + 1}/{len(chunks)}  chunk {chunk_id}")


if __name__ == "__main__":
    main()