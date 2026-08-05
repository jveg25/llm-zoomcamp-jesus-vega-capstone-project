"""FastAPI backend: HTTP wrapper around the RAG pipeline."""
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.rag import answer

import time
from app.history import log_conversation, questions_this_month, save_feedback
from common.config import settings
from typing import Literal

from app.auth import require_user, current_user, User
from app import admin

app = FastAPI(title="Personal Instructor")
app.include_router(admin.router)


@app.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    """Current user's identity + live role — the UI uses this to decide what to show."""
    return {"user_id": user.user_id, "email": user.email, "role": user.role}


class AskRequest(BaseModel):
    question: str

class Source(BaseModel):
    paper_id: int
    title: str
    section: str | None


class AskResponse(BaseModel):
    conversation_id: int
    answer: str
    answer_found: bool
    sources: list[Source]

@app.post("/ask")
def ask(req: AskRequest, user: User = Depends(require_user)) -> AskResponse:
    # Checked before anything else: an over-quota request must cost nothing, and
    # both retrieval and generation call OpenAI. Admins are exempt -- the cap
    # exists to bound what a shared demo account can spend, not to limit the
    # owner. Set MONTHLY_QUESTION_LIMIT=0 to turn it off.
    limit = settings.monthly_question_limit
    if limit and user.role != "admin":
        used = questions_this_month(user.user_id)
        if used >= limit:
            raise HTTPException(429, f"This account has used its {limit} "
                                     f"question{'' if limit == 1 else 's'} for the "
                                     f"month. The count resets on the 1st.")

    t0 = time.perf_counter()
    result = answer(req.question)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    conversation_id = log_conversation(req.question, result, elapsed_ms, user.user_id)

    cited = [result.hits[i - 1] for i in result.answer.citations
             if 1 <= i <= len(result.hits)]
    return AskResponse(
        conversation_id=conversation_id,
        answer=result.answer.answer,
        answer_found=result.answer.answer_found,
        sources=[Source(paper_id=h.paper_id, title=h.title, section=h.section)
                 for h in cited],
    )

class FeedbackRequest(BaseModel):
    conversation_id: int
    value: Literal[-1, 1]     # matches the DB CHECK constraint; FastAPI rejects anything else

@app.post("/feedback")
def feedback(req: FeedbackRequest, user: User = Depends(require_user)) -> dict:
    save_feedback(req.conversation_id, req.value, user.user_id)
    return {"status": "ok"}