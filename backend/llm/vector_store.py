import urllib.parse
from typing import List, Dict

from django.conf import settings
from langchain_community.vectorstores.pgvector import PGVector

from llm.bedrock import get_embeddings


def _connection_string():
    db = settings.DATABASES["default"]
    user = urllib.parse.quote(db["USER"])
    password = urllib.parse.quote(db["PASSWORD"])
    host = db["HOST"]
    port = db.get("PORT") or 5432
    name = db["NAME"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_vector_store(collection_name: str) -> PGVector:
    """
    Return a PGVector store bound to the given collection.
    """
    return PGVector(
        collection_name=collection_name,
        connection_string=_connection_string(),
        embedding_function=get_embeddings(),
    )


def upsert_project_embeddings(project_id: int, texts: List[str], metadatas: List[Dict]):
    store = get_vector_store(f"project-{project_id}")
    # Clean existing for this project_id in this collection
    store.delete(filter={"project_id": project_id})
    if texts:
        store.add_texts(texts=texts, metadatas=metadatas)


def retrieve_project_chunks(project_id: int, query: str, k: int = 20):
    store = get_vector_store(f"project-{project_id}")
    retriever = store.as_retriever(search_type="similarity", search_kwargs={"k": k})
    docs = retriever.get_relevant_documents(query)
    return docs

