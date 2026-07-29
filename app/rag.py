"""RAG answer generation: retrieve -> build prompt -> LLM -> structured answer."""

from pydantic import BaseModel
from openai import OpenAI

from common.config import settings

from app.search import Hit, hybrid_search

client = OpenAI(api_key=settings.openai_api_key)

class RagAnswer(BaseModel):
    answer: str
    answer_found: bool      # False -> feeds the unanswered-questions queue later
    citations: list[int]    # indices into the context blocks, e.g. [1, 3]


def build_prompt(question: str, hits: list[Hit]) -> str:
    context = "\n\n".join(
        f"[{i}] {h.title} — {h.section or 'n/a'}\n{h.content}"
        for i, h in enumerate(hits, 1)
    )
    return f"""You are an assistant answering questions about battery energy storage systems (BESS).

Answer the question using ONLY the context below.
- Cite the context blocks that support your answer by their number, e.g. [1] or [2][3], and list those numbers in `citations`.
- If the context does not contain enough information to answer, set `answer_found` to false, leave `citations` empty, and briefly say what is missing.
- Do not use outside knowledge.

Context:
{context}

Question: {question}"""


def answer(question: str, k: int = 5) -> tuple[RagAnswer, list[Hit]]:
    hits = hybrid_search(question, k=k)
    prompt = build_prompt(question, hits)
    resp = client.chat.completions.parse(          # structured output
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        response_format=RagAnswer,
    )
    return resp.choices[0].message.parsed, hits

if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "what factors drive the LCOS of battery storage?"
    result, hits = answer(q)
    print(f"answer_found: {result.answer_found}\n\n{result.answer}\n")
    for i, h in enumerate(hits, 1):
        mark = "*" if i in result.citations else " "
        print(f"{mark}[{i}] {h.title[:50]} — {h.section or '-'}")