import weaviate
from sentence_transformers import SentenceTransformer

from worker.agent_output import ResearchContext
from worker.core.llm import llm_complete
from worker.enums import Domain

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
        "You are a legal scholar drafting a passage from a law review article or case brief "
        "that addresses the question below. Reference relevant statutes or case law principles. "
        "Write 3-4 paragraphs.\n\nQuestion: {query}"
    ),
    Domain.TECHNICAL: (
        "You are a technical writer drafting a documentation page that answers the question below. "
        "Include specific implementation details, code/config examples, and best practices. "
        "Write 3-4 paragraphs.\n\nQuestion: {query}"
    ),
}


embed_model = None
client = None


def get_embed_model():
    global embed_model
    if embed_model is None:
        embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embed_model


def get_weaviate_client():
    global client
    if client is None:
        client = weaviate.connect_to_local()
    return client


async def generate_hypothetical_docs(
    query: str,
    domain: Domain,
    n: int = 3,
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

    # fallback: if LLM didn't split properly, treat whole output as one doc
    if not docs:
        docs = [response.content.strip()]

    return docs[:n]



async def create_hyde_embedddings(research_ctx: ResearchContext,n :int):
    request=research_ctx.request
    docs : list[str]=await generate_hypothetical_docs(request.query,request.domain,3)


def get_collection():
    