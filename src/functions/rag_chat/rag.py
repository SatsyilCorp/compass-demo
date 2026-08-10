"""Grounded RAG answer pipeline — retrieved grants + LLM, with citations.

Adapted from the ``satsyil_chatbot.answer`` building block
(the satsyil-blocks library, satsyil_chatbot), trimmed for Compass:
attachments support removed (no file uploads in /chat), chunk-key probing
simplified to the grant shape produced by ``retrieval.search_grants``. The
structure is unchanged: both heavy dependencies are injected

    retrieve_fn(question) -> list[grant row]      (pairs with retrieval.py)
    llm_fn(system, user)  -> str                  (pairs with compass_common.llm)

so the pipeline is pure orchestration and smoke-tests offline with fakes.
Citation tokens are grant numbers — the model is instructed to cite
``[ONRD-...]`` inline, and the returned citation index carries the grant
metadata the UI renders.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Sequence

Chunk = Mapping[str, Any]
RetrieveFn = Callable[[str], Sequence[Chunk]]
LlmFn = Callable[[str, str], str]

SYSTEM_PROMPT = (
    "You are Compass, the S&T portfolio intelligence assistant for a synthetic "
    "(mock) ONR research-grant portfolio. Answer the question concisely and "
    "specifically using ONLY the provided grant passages. Each passage is "
    "labelled with a citation token like [ONRD-2026-AIML-00123]; cite the "
    "token(s) you relied on inline after the statements they support. Never "
    "state or estimate dollar amounts — funding figures are access-controlled "
    "and not in your context. If the answer is not in the passages, say so "
    "plainly rather than guessing."
)

NO_CONTEXT_ANSWER = (
    "I could not retrieve any indexed grant abstracts visible to your "
    "organization for that question, so I can't give a grounded answer yet. "
    "Try again after the next ingest completes, or broaden the question."
)


def assemble_context(
    chunks: Sequence[Chunk],
    *,
    history: Optional[Sequence[Mapping[str, str]]] = None,
    max_chunk_chars: int = 1500,
    max_history_turns: int = 8,
) -> tuple[str, list[dict[str, Any]]]:
    """Build the grounded-context blob + citation index from retrieved grants.

    Returns ``(context_text, citations)``; each citation is
    ``{"grant_no", "title", "program_area", "fiscal_year", "awardee",
    "similarity", "snippet"}`` keyed by the same ``[grant_no]`` token rendered
    in ``context_text``.
    """
    citations: list[dict[str, Any]] = []
    blocks: list[str] = []

    for chunk in chunks:
        grant_no = str(chunk.get("grant_no") or "").strip()
        text = str(chunk.get("abstract") or "").strip()
        if not grant_no or not text:
            continue
        title = chunk.get("title")
        meta_bits = [
            str(x)
            for x in (
                chunk.get("program_area"),
                f"FY{chunk['fiscal_year']}" if chunk.get("fiscal_year") else None,
                chunk.get("awardee"),
            )
            if x
        ]
        header = f"[{grant_no}] {title or ''}".strip()
        if meta_bits:
            header += f" ({'; '.join(meta_bits)})"
        blocks.append(f"{header}\n{text[:max_chunk_chars]}")

        sim = chunk.get("similarity")
        citations.append(
            {
                "grant_no": grant_no,
                "title": title,
                "program_area": chunk.get("program_area"),
                "fiscal_year": chunk.get("fiscal_year"),
                "awardee": chunk.get("awardee"),
                "similarity": round(float(sim), 4) if sim is not None else None,
                "snippet": text[:240],
            }
        )

    parts: list[str] = []
    if history:
        turns = [
            f"{str(m.get('role', 'user')).upper()}: {str(m.get('content', '')).strip()}"
            for m in list(history)[-max_history_turns:]
            if str(m.get("content", "")).strip()
        ]
        if turns:
            parts.append("CONVERSATION SO FAR:\n" + "\n".join(turns))

    if blocks:
        parts.append(
            "GRANT PASSAGES (cite the [token] you use):\n\n" + "\n\n".join(blocks)
        )
    else:
        parts.append("GRANT PASSAGES:\nNo relevant passages were retrieved.")

    return "\n\n".join(parts), citations


def answer(
    question: str,
    retrieve_fn: RetrieveFn,
    llm_fn: LlmFn,
    *,
    history: Optional[Sequence[Mapping[str, str]]] = None,
    system_prompt: str = SYSTEM_PROMPT,
) -> Dict[str, Any]:
    """Retrieve grounded context for ``question`` and ask the LLM.

    Returns ``{"text", "citations", "chunks_used", "grounded"}``. When nothing
    is retrievable the model is NOT called — the honest no-context reply is
    returned with ``grounded: False`` (cheaper, and it cannot hallucinate).
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required and cannot be empty")

    chunks = list(retrieve_fn(question) or [])
    context_text, citations = assemble_context(chunks, history=history)

    if not citations:
        return {
            "text": NO_CONTEXT_ANSWER,
            "citations": [],
            "chunks_used": 0,
            "grounded": False,
        }

    user_message = f"{context_text}\n\nQUESTION: {question}"
    text = (llm_fn(system_prompt, user_message) or "").strip()
    return {
        "text": text,
        "citations": citations,
        "chunks_used": len(citations),
        "grounded": True,
    }
