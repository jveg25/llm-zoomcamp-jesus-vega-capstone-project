"""FastAPI backend: HTTP wrapper around the RAG pipeline."""
from fastapi import FastAPI
from pydantic import BaseModel

from app.rag import answer

import time
from app.history import log_conversation, save_feedback
from typing import Literal

app = FastAPI(title="Personal Instructor")


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
def ask(req: AskRequest) -> AskResponse:
    t0 = time.perf_counter()
    result = answer(req.question)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    conversation_id = log_conversation(req.question, result, elapsed_ms)

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
def feedback(req: FeedbackRequest) -> dict:
    save_feedback(req.conversation_id, req.value)
    return {"status": "ok"}