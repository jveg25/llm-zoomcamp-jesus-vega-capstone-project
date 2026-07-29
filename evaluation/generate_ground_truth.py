"""Generate a ground-truth dataset: questions whose source chunk is known."""
import asyncio
import csv
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel

from common.config import settings
from common.db import get_connection

client = AsyncOpenAI(api_key=settings.openai_api_key)
CONCURRENCY = 8         # max requests in flight at once
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
            WHERE length(c.content) > 300      -- skip fragments: no meaningful questions
            ORDER BY c.id
        """)
        return cur.fetchall()


async def gen_questions(sem: asyncio.Semaphore, chunk: tuple) -> tuple[int, int, list[str]]:
    chunk_id, paper_id, title, section, content = chunk
    async with sem:     # waits here if CONCURRENCY requests are already in flight
        resp = await client.chat.completions.parse(
            model=settings.llm_model,
            messages=[{"role": "user", "content": PROMPT.format(
                title=title, section=section or "n/a", content=content)}],
            response_format=Questions,
        )
    return chunk_id, paper_id, resp.choices[0].message.parsed.questions


async def run(chunks: list[tuple], writer, f) -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [gen_questions(sem, c) for c in chunks]
    for i, task in enumerate(asyncio.as_completed(tasks), 1):
        chunk_id, paper_id, questions = await task
        for q in questions:
            writer.writerow([q, chunk_id, paper_id])
        f.flush()                              # crash-safe: each chunk lands immediately
        print(f"{i}/{len(tasks)}  chunk {chunk_id}")


def main() -> None:
    done = set()
    if OUT.exists():                           # resumable: skip chunks already processed
        with OUT.open() as f:
            done = {int(row["chunk_id"]) for row in csv.DictReader(f)}

    todo = [c for c in fetch_chunks() if c[0] not in done]
    print(f"{len(todo)} chunks to process ({len(done)} already done)")
    with OUT.open("a", newline="") as f:
        writer = csv.writer(f)
        if not done:
            writer.writerow(["question", "chunk_id", "paper_id"])
        asyncio.run(run(todo, writer, f))


if __name__ == "__main__":
    main()