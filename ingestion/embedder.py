from openai import OpenAI

from common.config import settings

client = OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Embed texts in batches; returns vectors in the same order as the input."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=settings.embedding_model, input=batch)
        vectors.extend(d.embedding for d in resp.data)
    return vectors