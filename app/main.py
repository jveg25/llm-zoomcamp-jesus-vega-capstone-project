"""FastAPI backend: HTTP wrapper around the RAG pipeline."""
from fastapi import FastAPI
from pydantic import BaseModel

from app.rag import answer

app = FastAPI(title="Personal Instructor")


class AskRequest(BaseModel):
    question: str


class Source(BaseModel):
    paper_id: int
    title: str
    section: str | None


class AskResponse(BaseModel):
    answer: str
    answer_found: bool
    sources: list[Source]

@app.post("/ask")
def ask(req: AskRequest) -> AskResponse:
    result, hits = answer(req.question)
    cited = [hits[i - 1] for i in result.citations if 1 <= i <= len(hits)]
    return AskResponse(
        answer=result.answer,
        answer_found=result.answer_found,
        sources=[Source(paper_id=h.paper_id, title=h.title, section=h.section)
                 for h in cited],
    )