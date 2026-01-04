import os
from typing import Optional

from django.conf import settings
from langchain_aws import BedrockLLM, BedrockEmbeddings


def get_llm(model_id: Optional[str] = None):
    return BedrockLLM(
        model_id=model_id or settings.BEDROCK_TEXT_MODEL,
        region_name=settings.BEDROCK_REGION,
    )


def get_embeddings(model_id: Optional[str] = None):
    return BedrockEmbeddings(
        model_id=model_id or settings.BEDROCK_EMBEDDING_MODEL,
        region_name=settings.BEDROCK_REGION,
    )

