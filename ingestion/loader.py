from pgvector import Vector

from common.db import get_connection
from ingestion.chunker import Chunk


def load_paper(
    filename: str,
    title: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> int | None:
    """Insert a paper + its chunks. Returns paper_id, or None if already ingested."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM papers WHERE filename = %s", (filename,))
        if cur.fetchone():
            return None                       # idempotency: skip what's already in

        cur.execute(
            "INSERT INTO papers (filename, title) VALUES (%s, %s) RETURNING id",
            (filename, title),
        )
        paper_id = cur.fetchone()[0]

        for chunk, emb in zip(chunks, embeddings, strict=True):
            cur.execute(
                """
                INSERT INTO chunks
                    (paper_id, chunk_index, section, page_start, page_end, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (paper_id, chunk.index, chunk.section, chunk.page_start,
                 chunk.page_end, chunk.content, Vector(emb)),
            )
    return paper_id