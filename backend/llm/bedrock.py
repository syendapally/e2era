import os
from typing import Optional

import boto3
from botocore.config import Config
from django.conf import settings
from langchain_aws import BedrockLLM, BedrockEmbeddings


def _bedrock_client():
    # Shorter timeouts to avoid hanging Gunicorn workers on upstream issues
    cfg = Config(
        connect_timeout=5,
        read_timeout=20,
        retries={"max_attempts": 2, "mode": "standard"},
    )
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.BEDROCK_REGION,
        config=cfg,
    )


def get_llm(model_id: Optional[str] = None):
    return BedrockLLM(
        client=_bedrock_client(),
        model_id=model_id or settings.BEDROCK_TEXT_MODEL,
    )


def get_embeddings(model_id: Optional[str] = None):
    return BedrockEmbeddings(
        client=_bedrock_client(),
        model_id=model_id or settings.BEDROCK_EMBEDDING_MODEL,
    )

