from typing import List

from django.core.files.storage import default_storage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader

from core.models import Document
from llm.vector_store import upsert_project_embeddings


def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def chunk_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_text(text)


def embed_document(document: Document):
    local_path = default_storage.path(document.file.name)
    text = extract_text_from_pdf(local_path)
    chunks = chunk_text(text)
    metadatas = [
        {"project_id": document.project_id, "document_id": document.id, "chunk_index": idx}
        for idx, _ in enumerate(chunks)
    ]
    upsert_project_embeddings(document.project_id, chunks, metadatas)
    document.text_extracted = True
    document.save(update_fields=["text_extracted"])

