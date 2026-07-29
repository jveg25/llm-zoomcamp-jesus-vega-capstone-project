"""RAG answer generation: retrieve -> build prompt -> LLM -> structured answer."""

from pydantic import BaseModel
from openai import OpenAI

from common.config import settings

from app.search import Hit, hybrid_search
from dataclasses import dataclass

client = OpenAI(api_key=settings.openai_api_key)


PROMPTS = {
    "v1": """You are an assistant answering questions about battery energy storage systems (BESS).

Answer the question using ONLY the context below.
- Cite the context blocks that support your answer by their number, e.g. [1] or [2][3], and list those numbers in `citations`.
- If the context does not contain enough information to answer, set `answer_found` to false, leave `citations` empty, and briefly say what is missing.
- Do not use outside knowledge.

Context:
{context}

Question: {question}""",

    "v2": """You are a technical instructor for battery energy storage systems (BESS).
Answer the question using ONLY the context below.
- Start with a direct 1-2 sentence answer, then add supporting detail.
- Quote exact figures and units from the context when available.
- Cite context blocks as [n] and list them in `citations`.
- If the context is insufficient, set answer_found to false and state what is missing.
- Never use outside knowledge.

Context:
{context}

Question: {question}""",
}

class RagAnswer(BaseModel):
    answer: str
    answer_found: bool      # False -> feeds the unanswered-questions queue later
    citations: list[int]    # indices into the context blocks, e.g. [1, 3]

@dataclass
class RagResult:
    answer: RagAnswer
    hits: list[Hit]
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

def build_prompt(question: str, hits: list[Hit], version: str = "v1") -> str:
    context = "\n\n".join(
        f"[{i}] {h.title} — {h.section or 'n/a'}\n{h.content}"
        for i, h in enumerate(hits, 1)
    )
    return PROMPTS[version].format(context=context, question=question)


def answer(question: str, k: int = 5, prompt_version: str = "v1") -> RagResult:
    hits = hybrid_search(question, k=k)
    prompt = build_prompt(question, hits, prompt_version)
    resp = client.chat.completions.parse(          # structured output
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        response_format=RagAnswer,
    )
    usage = resp.usage
    cost = (usage.prompt_tokens * settings.price_prompt_per_1m
            + usage.completion_tokens * settings.price_completion_per_1m) / 1_000_000
    return RagResult(
        answer=resp.choices[0].message.parsed,
        hits=hits,
        model=settings.llm_model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        cost_usd=cost,
    )

if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "what factors drive the LCOS of battery storage?"
    result, hits = answer(q)
    print(f"answer_found: {result.answer_found}\n\n{result.answer}\n")
    for i, h in enumerate(hits, 1):
        mark = "*" if i in result.citations else " "
        print(f"{mark}[{i}] {h.title[:50]} — {h.section or '-'}")