import os
import time

from sentence_transformers import SentenceTransformer
from weaviate.classes.data import DataObject
from weaviate.classes.query import MetadataQuery

from worker.agent_output import ResearchContext
from worker.core.llm import llm_complete
from worker.db.collections import ensure_collection, ChunkPayload
from worker.enums import Domain

MIN_SIMILARITY = float(os.getenv("HYDE_MIN_SIMILARITY", "0.70"))

HYDE_PROMPTS = {
    Domain.GENERAL: (
        "You are generating a hypothetical document that would be the perfect answer "
        "to the question below. Write 3-4 paragraphs of informative, well-structured content. "
        "Be specific and factual. Do not reference any real sources by name.\n\nQuestion: {query}"
    ),
    Domain.MEDICAL: (
        "You are a medical researcher drafting a passage from a peer-reviewed clinical study "
        "that fully answers the question below. Include mechanisms, statistical findings, "
        "and clinical implications where appropriate. Write 3-4 paragraphs.\n\nQuestion: {query}"
    ),
    Domain.LEGAL: (
        "You are a legal holar drafting a passage from a law review article or case brief "
        "that addresses the question below. Reference relevant statutes or case law principles. "
        "Write 3-4 paragraphs.\n\nQuestion: {query}"
    ),
    Domain.TECHNICAL: (
        "You are a technical writer drafting a documentation page that answers the question below. "
        "Include specific implementation details, code/config examples, and best practices. "
        "Write 3-4 paragraphs.\n\nQuestion: {query}"
    ),
}

_embed_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


async def generate_hypothetical_docs(
    query: str,
    domain: Domain,
    n: int = 1,
) -> list[str]:
    template = HYDE_PROMPTS.get(domain, HYDE_PROMPTS[Domain.GENERAL])
    prompt = template.format(query=query)

    full_prompt = (
        f"{prompt}\n\n"
        f"Generate {n} different versions, each covering a distinct aspect or perspective. "
        f"Separate each version with '---DOC---' on its own line. "
        f"Do not number them."
    )

    response = await llm_complete(prompt=full_prompt)
    docs = [d.strip() for d in response.content.split("---DOC---") if d.strip()]

    if not docs:
        docs = [response.content.strip()]

    return docs[:n]


async def search_by_hyde(research_ctx: ResearchContext, n: int) -> list[dict[str, str]]:
    max_distance = 1.0 - MIN_SIMILARITY
    request = research_ctx.request
    docs = await generate_hypothetical_docs(request.query, request.domain, 3)
    col = ensure_collection()

    vectors = get_embed_model().encode(docs).tolist()

    seen_urls: set[str] = set()
    deduped: list[dict[str, str]] = []
    for vec in vectors:
        response = col.query.near_vector(
            near_vector=vec,
            limit=n,
            return_metadata=MetadataQuery(distance=True),
        )
        for obj in response.objects:
            distance = obj.metadata.distance
            if distance is not None and distance > max_distance:
                continue
            url = obj.properties["sourceUrl"]
            if url not in seen_urls:
                seen_urls.add(url)
                deduped.append({
                    "url": url,
                    "title": obj.properties.get("title", ""),
                    "snippet": obj.properties.get("chunkText", "")[:300],
                    "domain": obj.properties.get("domain", ""),
                    "from_hyde": "true",
                })

    return deduped


def index_chunks(ctx: ResearchContext) -> None:
    all_texts: list[str] = []
    payloads: list[ChunkPayload] = []

    for url, chunks in ctx.chunks.items():
        for idx, chunk_text in enumerate(chunks):
            all_texts.append(chunk_text)
            payloads.append(ChunkPayload(
                chunkText=chunk_text,
                sourceUrl=url,
                domain=ctx.request.domain.value,
                originalQuery=ctx.request.query,
                title=ctx.search_results[url].get("title", ""),
                chunkIndex=idx,
                createdAt=time.time(),
            ))

    if not all_texts:
        return

    vectors = get_embed_model().encode(all_texts).tolist()
    col = ensure_collection()

    col.data.insert_many([
        DataObject(properties=p.model_dump(), vector=v)
        for p, v in zip(payloads, vectors)
    ])
