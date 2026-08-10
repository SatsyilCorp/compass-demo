"""Bedrock-only LLM gateway — the single in-boundary model chokepoint.

Compass narrates an IL5 boundary story: **no public Anthropic API in any
recorded path**. Every model call in this module goes through Amazon Bedrock,
using the two contract models:

  * chat / summary  → ``amazon.nova-lite-v1:0``   via the Converse API
  * embeddings      → ``amazon.titan-embed-text-v2:0`` via InvokeModel (1024-dim,
                      matching ``grants_curated.abstract_embedding vector(1024)``)

Adapted from the ``satsyil_llm`` ``bedrock_transport`` block: a module-level
**cached** ``bedrock-runtime`` client built with explicit connect/read timeouts
(10s / 30s) and adaptive retry, so a hung inference call can't block the whole
Lambda invocation, and warm invocations reuse the client.

boto3 is imported lazily inside the client factory, so this module imports — and
the smoke test runs — with no boto3, no network, and no credentials. Inject a
fake ``client_factory`` (any object exposing ``.converse`` / ``.invoke_model``)
to exercise the gateway offline.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from . import config

_BEDROCK_CLIENT = None


def get_bedrock_client(
    *, connect_timeout: int = 10, read_timeout: int = 30, max_attempts: int = 3
):
    """Module-level cached ``bedrock-runtime`` client for warm reuse.

    Explicit timeouts (boto3's default 60s read lets a hung request block the
    invocation) and adaptive retry (throttle-aware — the right default for
    inference). Region comes from config (default us-east-1).
    """
    global _BEDROCK_CLIENT
    if _BEDROCK_CLIENT is None:
        import boto3
        from botocore.config import Config as BotoConfig

        cfg = BotoConfig(
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            retries={"max_attempts": max_attempts, "mode": "adaptive"},
        )
        _BEDROCK_CLIENT = boto3.client(
            "bedrock-runtime", region_name=config.aws_region(), config=cfg
        )
    return _BEDROCK_CLIENT


def converse(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: int = 800,
    temperature: float = 0.0,
    client_factory: Callable[[], Any] = get_bedrock_client,
) -> Dict[str, Any]:
    """One chat/summary turn via Bedrock Converse (nova-lite by default).

    Returns ``{"text": str, "usage": {...}|None, "model_id": str}``. The
    provider-neutral single-user-message shape is reshaped to Bedrock's
    ``content:[{"text":...}]`` form here.
    """
    model_id = model or config.bedrock_chat_model()
    resp = client_factory().converse(
        modelId=model_id,
        system=[{"text": system}] if system else [],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return {"text": text, "usage": resp.get("usage"), "model_id": model_id}


def embed(
    text: str,
    *,
    model: Optional[str] = None,
    dimensions: int = config.EMBED_DIMENSIONS_DEFAULT,
    normalize: bool = True,
    client_factory: Callable[[], Any] = get_bedrock_client,
) -> List[float]:
    """Embed one string via Titan Embed Text v2 → a ``dimensions``-length vector.

    Defaults to 1024 dimensions so the result drops straight into the
    ``vector(1024)`` column. Raises ``ValueError`` on empty input rather than
    silently returning a zero vector.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("embed requires non-empty text")
    model_id = model or config.bedrock_embed_model()
    body = json.dumps(
        {"inputText": text, "dimensions": dimensions, "normalize": normalize}
    )
    resp = client_factory().invoke_model(
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
        body=body,
    )
    payload = json.loads(resp["body"].read())
    return payload["embedding"]


def embed_batch(
    texts: List[str],
    *,
    model: Optional[str] = None,
    dimensions: int = config.EMBED_DIMENSIONS_DEFAULT,
    normalize: bool = True,
    client_factory: Callable[[], Any] = get_bedrock_client,
) -> List[List[float]]:
    """Embed a list of strings (Titan v2 is single-input; this loops honestly)."""
    return [
        embed(
            t,
            model=model,
            dimensions=dimensions,
            normalize=normalize,
            client_factory=client_factory,
        )
        for t in texts
    ]


def reset_cache() -> None:
    """Drop the cached Bedrock client (used between tests)."""
    global _BEDROCK_CLIENT
    _BEDROCK_CLIENT = None
