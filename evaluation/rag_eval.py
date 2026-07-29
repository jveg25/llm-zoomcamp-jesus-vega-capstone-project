"""RAG answer evaluation: generate answers per prompt variant, LLM-as-judge scores them."""
import csv
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from app.rag import answer
from common.config import settings

judge_client = OpenAI(api_key=settings.openai_api_key)
SAMPLE_SIZE = 150
SEED = 42                    # same sample every run -> variants stay comparable
WORKERS = 8

JUDGE_PROMPT = """You are evaluating a RAG system's answer.

Question: {question}

Generated answer: {answer}

Classify the answer's relevance to the question:
- RELEVANT: directly and substantively answers the question
- PARTLY_RELEVANT: on topic but incomplete, vague, or partially off
- NON_RELEVANT: does not answer the question (a justified "the context lacks this" counts as NON_RELEVANT)

Provide a one-sentence explanation."""


class Judgment(BaseModel):
    relevance: Literal["RELEVANT", "PARTLY_RELEVANT", "NON_RELEVANT"]
    explanation: str


def judge(question: str, generated: str) -> Judgment:
    resp = judge_client.chat.completions.parse(
        model=settings.llm_model,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(
            question=question, answer=generated)}],
        response_format=Judgment,
    )
    return resp.choices[0].message.parsed

def eval_one(row: dict, version: str) -> list:
    result = answer(row["question"], prompt_version=version)
    j = judge(row["question"], result.answer.answer)
    return [version, row["question"], result.answer.answer_found,
            j.relevance, j.explanation, result.cost_usd]


def main(version: str) -> None:
    out = Path(f"evaluation/rag_eval_{version}.csv")
    with Path("evaluation/ground_truth.csv").open() as f:
        gt = list(csv.DictReader(f))
    random.seed(SEED)
    sample = random.sample(gt, SAMPLE_SIZE)

    done = set()
    if out.exists():
        with out.open() as f:
            done = {r["question"] for r in csv.DictReader(f)}
    todo = [r for r in sample if r["question"] not in done]
    print(f"{version}: {len(todo)} to evaluate ({len(done)} done)")

    with out.open("a", newline="") as f:
        writer = csv.writer(f)
        if not done:
            writer.writerow(["version", "question", "answer_found",
                             "relevance", "explanation", "cost_usd"])
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for i, res in enumerate(pool.map(lambda r: eval_one(r, version), todo), 1):
                writer.writerow(res)
                f.flush()
                print(f"{i}/{len(todo)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v1")