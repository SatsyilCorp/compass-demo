"""RAG chat Lambda - POST /chat (element 6, docs/CONTRACTS.md).

Flow (all in-boundary, Bedrock only - no public LLM API):
  1. Authenticate via the authorizer-injected claims (deny-by-default).
  2. Embed the question with Titan Embed Text v2 (1024-dim) through the
     ``compass_common.llm`` gateway.
  3. Retrieve the top-k curated grants by pgvector cosine similarity - INSIDE
     ``db.set_org(conn, claims.org_unit)``, so row-level security filters
     retrieval to the caller's org (Code-30 viewer sees only Code-30 grants;
     ONR-Corporate sees all). The answer respects RLS by construction: the
     model never receives a passage the caller could not SELECT.
  4. Answer with Nova Lite via the Bedrock Converse API, grounded on the
     retrieved abstracts, citing grant numbers inline.

Request  : {"message": str, "history": [{"role","content"}]?, "top_k": 1..12?}
           ("question" accepted as an alias of "message")
Response : {"answer": str, "citations": [{"grant_no","title","program_area",
            "fiscal_year","awardee","similarity","snippet"}],
            "chunks_used": int, "grounded": bool, "model": str,
            "model_id": str|null, "org_unit": str}

CLS note: ``amount_usd`` is never selected (column-revoked from compass_app),
and the system prompt forbids the model from estimating dollar figures.
"""
from __future__ import annotations

import logging
import os

from compass_common import config, db, http, llm

import rag
import retrieval

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

DEFAULT_TOP_K = 6
MAX_TOP_K = 12
MAX_QUESTION_CHARS = 2000


def handler(event, context):
    try:
        claims = http.get_claims(event)
        if not claims.is_authenticated:
            return http.unauthorized()

        body = http.parse_body(event)
        # The frontend contract (lib/types.ts ChatRequest) sends `message`;
        # `question` is accepted as an alias for direct/curl callers.
        question = str(body.get("message") or body.get("question") or "").strip()
        if not question:
            return http.bad_request("'message' is required")
        if len(question) > MAX_QUESTION_CHARS:
            return http.bad_request(f"'question' exceeds {MAX_QUESTION_CHARS} characters")

        history = body.get("history") or []
        if not isinstance(history, list) or not all(isinstance(m, dict) for m in history):
            return http.bad_request("'history' must be a list of {role, content} objects")

        try:
            top_k = int(body.get("top_k", DEFAULT_TOP_K))
        except (TypeError, ValueError):
            return http.bad_request("'top_k' must be an integer")
        top_k = max(1, min(top_k, MAX_TOP_K))

        # 1) Embed the question (Titan v2, 1024-dim - matches the column type).
        query_embedding = llm.embed(question)

        # 2) Retrieve under the caller's RLS context.
        conn = db.get_conn()
        with db.set_org(conn, claims.org_unit) as c:
            grants = retrieval.search_grants(c, query_embedding, top_k=top_k)

        # 3) Grounded answer via Nova Lite (skipped when nothing retrieved).
        result = rag.answer(
            question,
            retrieve_fn=lambda _q: grants,
            llm_fn=lambda system, user: llm.converse(
                system=system, user=user, max_tokens=800, temperature=0.0
            )["text"],
            history=history,
        )

        logger.info(
            "chat answered for org=%s: %s chunks, grounded=%s",
            claims.org_unit, result["chunks_used"], result["grounded"],
        )
        model_id = config.bedrock_chat_model() if result["grounded"] else None
        return http.ok(
            {
                "answer": result["text"],
                "citations": result["citations"],
                "chunks_used": result["chunks_used"],
                "grounded": result["grounded"],
                # `model` is the frontend contract field (lib/types.ts
                # ChatResponse); `model_id` kept for machine callers.
                "model": model_id or "none (no grounded retrieval)",
                "model_id": model_id,
                "org_unit": claims.org_unit,
            }
        )
    except ValueError as e:
        return http.bad_request(str(e))
    except Exception:
        logger.exception("rag_chat handler failed")
        return http.server_error()
