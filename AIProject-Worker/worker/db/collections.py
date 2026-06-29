import os
from urllib.parse import urlparse

import weaviate
from pydantic import BaseModel
from weaviate.collections import Collection
from weaviate.collections.classes.config import Property, DataType

COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ResearchChunk")

PROPERTIES = [
    Property(name="chunkText", data_type=DataType.TEXT, skip_vectorization=True),
    Property(name="sourceUrl", data_type=DataType.TEXT),
    Property(name="domain", data_type=DataType.TEXT),
    Property(name="originalQuery", data_type=DataType.TEXT),
    Property(name="title", data_type=DataType.TEXT),
    Property(name="chunkIndex", data_type=DataType.INT),
    Property(name="createdAt", data_type=DataType.NUMBER),
]


class ChunkPayload(BaseModel):
    chunkText: str
    sourceUrl: str
    domain: str
    originalQuery: str
    title: str
    chunkIndex: int
    createdAt: float


_client = None


def get_weaviate_client():
    global _client
    if _client is None:
        raw = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        parsed = urlparse(raw)
        host = parsed.hostname or "localhost"
        http_port = parsed.port or 8080
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        _client = weaviate.connect_to_custom(
            http_host=host,
            http_port=http_port,
            http_secure=parsed.scheme == "https",
            grpc_host=host,
            grpc_port=grpc_port,
            grpc_secure=False,
        )
    return _client


def ensure_collection() -> Collection:
    client = get_weaviate_client()
    if client.collections.exists(COLLECTION_NAME):
        return client.collections.get(COLLECTION_NAME)
    return client.collections.create(
        name=COLLECTION_NAME,
        vectorizer_config=None,
        properties=PROPERTIES,
    )
