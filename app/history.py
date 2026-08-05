"""Persist conversations, failed answers, and feedback."""
from common.db import get_connection
from app.rag import RagResult


def log_conversation(question: str, result: RagResult, response_time_ms: int, user_id: str) -> int:
    """Insert the conversation (and the unanswered-question row if needed). Returns id."""
    top_score = result.hits[0].score if result.hits else None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO conversations
                (user_id, question, answer, model, prompt_tokens, completion_tokens,
                 cost_usd, response_time_ms, retrieval_score, answer_found)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, question, result.answer.answer, result.model, result.prompt_tokens,
             result.completion_tokens, result.cost_usd, response_time_ms,
             top_score, result.answer.answer_found),
        )
        conversation_id = cur.fetchone()[0]

        if not result.answer.answer_found:
            cur.execute(
                "INSERT INTO unanswered_questions (conversation_id, question) VALUES (%s, %s)",
                (conversation_id, question),
            )
    return conversation_id


def questions_this_month(user_id: str) -> int:
    """How many questions this account has asked since the 1st.

    Counts conversations rather than tokens or cost: it is the number a person
    can be told ("42 of 500 used") and it cannot be gamed by asking longer
    questions. The window is the calendar month, so the count resets on its own.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM conversations "
            "WHERE user_id = %s AND created_at >= date_trunc('month', now())",
            (user_id,),
        )
        return cur.fetchone()[0]


def save_feedback(conversation_id: int, value: int, user_id: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (conversation_id, value, user_id) VALUES (%s, %s, %s)",
            (conversation_id, value, user_id),
        )
