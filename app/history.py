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


def save_feedback(conversation_id: int, value: int, user_id: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (conversation_id, value, user_id) VALUES (%s, %s, %s)",
            (conversation_id, value, user_id),
        )
