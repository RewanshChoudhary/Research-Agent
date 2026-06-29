import weaviate
from dotenv import load_dotenv
from pydantic import BaseModel
from weaviate.collections import Collection
from weaviate.collections.classes.config import Property, DataType

from worker.core.hyde import get_weaviate_client

COLLECTION_NAME = load_dotenv("COLLECTION_NAME")

client=get_weaviate_client()

# Single source of truth for property definitions
PROPERTIES = [
    Property(name="chunkText",    data_type=DataType.TEXT,   skip_vectorization=True),
    Property(name="sourceUrl",    data_type=DataType.TEXT),
    Property(name="domain",       data_type=DataType.TEXT),
    Property(name="originalQuery",data_type=DataType.TEXT),
    Property(name="title",        data_type=DataType.TEXT),
    Property(name="chunkIndex",   data_type=DataType.INT),
    Property(name="createdAt",    data_type=DataType.NUMBER),
]

class ChunkPayload(BaseModel):
    chunkText:str
    sourceUrl:str
    domain:str
    originalQuery:str
    title:str
    chunkIndex:int

def ensure_collection()->Collection:
    if client.collections.exists(COLLECTION_NAME):
        return client.collections.get(COLLECTION_NAME)
    return client.collections.create(
        name=COLLECTION_NAME,
        vectorizer_config=None,
        properties=PROPERTIES,

    )




