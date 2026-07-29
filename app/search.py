"""Retrieval over the chunks table: vector, full-text, and hybrid (RRF)."""
from dataclasses import dataclass

from pgvector import Vector

from common.db import get_connection
from ingestion.embedder import embed_texts

import re


@dataclass
class Hit:
    chunk_id: int
    paper_id: int
    title: str
    section: str | None
    content: str
    score: float



def vector_search(query: str, k: int = 20) -> list[Hit]:
    """Semantic search: cosine distance between query embedding and chunk embeddings."""
    emb = Vector(embed_texts([query])[0])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
        """
        SELECT c.id, c.paper_id, p.title, c.section, c.content,
            1 - (c.embedding <=> %s) AS score
        FROM chunks c JOIN papers p ON p.id = c.paper_id
        ORDER BY c.embedding <=> %s
        LIMIT %s
        """,
        (emb, emb, k),
        )
        return [Hit(*row) for row in cur.fetchall()]
    


def text_search(query: str, k: int = 20) -> list[Hit]:
    """Keyword search over the generated tsvector column (terms OR'd for recall)."""
    terms = " | ".join(re.findall(r"\w+", query))   # 'factors | drive | lcos | ...'
    if not terms:
        return []
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.paper_id, p.title, c.section, c.content,
                   ts_rank(c.tsv, q) AS score
            FROM chunks c JOIN papers p ON p.id = c.paper_id,
                 to_tsquery('english', %s) q
            WHERE c.tsv @@ q
            ORDER BY score DESC
            LIMIT %s
            """,
            (terms, k),
        )
        return [Hit(*row) for row in cur.fetchall()]
 
 
RRF_K = 60   # standard damping constant: softens the gap between rank 1 and rank 2


def hybrid_search(query: str, k: int = 10) -> list[Hit]:
    """Merge vector and text results by rank (RRF), not by score."""
    fused: dict[int, tuple[float, Hit]] = {}      # chunk_id -> (rrf_score, hit)
    for results in (vector_search(query), text_search(query)):
        for rank, hit in enumerate(results, start=1):
            score = fused.get(hit.chunk_id, (0.0, hit))[0] + 1 / (RRF_K + rank)
            fused[hit.chunk_id] = (score, hit)

    ranked = sorted(fused.values(), key=lambda t: t[0], reverse=True)
    return [Hit(h.chunk_id, h.paper_id, h.title, h.section, h.content, score)
            for score, h in ranked[:k]]


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) or "what factors drive the LCOS of battery storage?"
    for name, fn in [("VECTOR", vector_search), ("TEXT", text_search), ("HYBRID", hybrid_search)]:
        print(f"\n=== {name}: {query}")
        for h in fn(query)[:5]:
            preview = " ".join(h.content.split())[:120]
            print(f"{h.score:.3f}  [{h.paper_id}] {h.title[:35]:35} | {h.section or '-':30} | {preview}")