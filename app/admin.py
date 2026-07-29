"""Admin-only endpoints: user management, document management, and the
human-in-the-loop review queue. Every route requires role = admin."""
from fastapi import APIRouter, Depends, HTTPException
from pgvector import Vector
from pydantic import BaseModel

from app.auth import User, require_admin
from common.db import get_connection
from ingestion.embedder import embed_texts

# Router-level dependency: no route here is reachable without an admin JWT.
router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

ROLES = ("pending", "user", "admin")


# ---------- User management ----------

class RoleUpdate(BaseModel):
    role: str


@router.get("/users")
def list_users() -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT user_id, email, role, created_at FROM profiles ORDER BY created_at")
        rows = cur.fetchall()
    return [{"user_id": str(r[0]), "email": r[1], "role": r[2],
             "created_at": r[3].isoformat()} for r in rows]


@router.post("/users/{user_id}/role")
def set_role(user_id: str, body: RoleUpdate, user: User = Depends(require_admin)) -> dict:
    if body.role not in ROLES:
        raise HTTPException(400, f"Role must be one of {ROLES}")
    if user_id == user.user_id:
        raise HTTPException(400, "You cannot change your own role.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE profiles SET role = %s WHERE user_id = %s", (body.role, user_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "User not found")
    return {"status": "ok"}


# ---------- Document management ----------

@router.get("/documents")
def list_documents() -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT p.id, p.title, p.filename, count(c.id) AS chunks, p.ingested_at
            FROM papers p LEFT JOIN chunks c ON c.paper_id = p.id
            GROUP BY p.id ORDER BY p.id
        """)
        rows = cur.fetchall()
    return [{"id": r[0], "title": r[1], "filename": r[2], "chunks": r[3],
             "ingested_at": r[4].isoformat()} for r in rows]


@router.delete("/documents/{paper_id}")
def delete_document(paper_id: int) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM papers WHERE id = %s", (paper_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Paper not found")
    return {"status": "deleted"}   # chunks removed via ON DELETE CASCADE


# ---------- Human-in-the-loop review queue ----------

class AnswerIntegrate(BaseModel):
    answer: str


@router.get("/unanswered")
def list_unanswered() -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, question, status, human_answer
            FROM unanswered_questions
            WHERE status != 'integrated'
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
    return [{"id": r[0], "question": r[1], "status": r[2], "human_answer": r[3]}
            for r in rows]


@router.post("/unanswered/{item_id}/integrate")
def integrate_answer(item_id: int, body: AnswerIntegrate,
                     user: User = Depends(require_admin)) -> dict:
    """Save the admin's answer AND embed it into the KB so the agent answers it next time."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT question FROM unanswered_questions WHERE id = %s", (item_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Queue item not found")
        question = row[0]

        content = f"Question: {question}\nAnswer: {body.answer}"
        emb = embed_texts([content])[0]

        # A single synthetic 'paper' collects all admin-curated Q&A chunks.
        cur.execute("SELECT id FROM papers WHERE filename = %s", ("__admin_answers__",))
        prow = cur.fetchone()
        if prow:
            paper_id = prow[0]
        else:
            cur.execute(
                "INSERT INTO papers (filename, title) VALUES (%s, %s) RETURNING id",
                ("__admin_answers__", "Admin-curated answers"),
            )
            paper_id = cur.fetchone()[0]

        cur.execute("SELECT coalesce(max(chunk_index), -1) + 1 FROM chunks WHERE paper_id = %s",
                    (paper_id,))
        chunk_index = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO chunks (paper_id, chunk_index, section, kind, content, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (paper_id, chunk_index, question[:200], "qa", content, Vector(emb)))

        cur.execute("""
            UPDATE unanswered_questions
            SET status = 'integrated', human_answer = %s, answered_by = %s, updated_at = now()
            WHERE id = %s
        """, (body.answer, user.user_id, item_id))

    return {"status": "integrated", "paper_id": paper_id}
