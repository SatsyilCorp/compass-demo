"use client";

import { useRef, useState } from "react";
import { CornerDownLeft, Loader2, MessageSquareQuote, Quote, Sparkles } from "lucide-react";

import { postChat } from "@/lib/api";
import type { ChatCitation, ChatMessage } from "@/lib/types";

import { useCompassAction } from "./use-compass-query";

/**
 * Natural-language Q&A over the curated portfolio — `POST /chat` (element 6).
 *
 * Three things this deliberately shows an evaluator:
 *   1. **Citations, always.** Every answer renders the rows it was grounded in
 *      (grant_no + title + snippet). An answer with no citations renders as an
 *      answer with no citations — the UI never implies sourcing that isn't in
 *      the response.
 *   2. **Same security scope as everything else.** Retrieval runs over rows the
 *      caller can see; switching persona changes what the assistant can cite.
 *   3. **Which model answered.** The `model` field from the response is shown
 *      verbatim, so the in-boundary Bedrock path is visible rather than
 *      asserted.
 */
const SUGGESTIONS = [
  "Where is autonomous systems investment concentrated?",
  "Summarize undersea warfare work in the portfolio.",
  "Which directed energy grants should I review first?",
];

type Turn = {
  id: number;
  question: string;
  answer: string;
  citations: ChatCitation[];
  model: string;
};

export function AskCompass({ scopeLabel }: { scopeLabel: string }) {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const nextId = useRef(1);
  const { run, pending, error } = useCompassAction(postChat);

  async function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || pending) return;
    const history: ChatMessage[] = turns.flatMap((t) => [
      { role: "user" as const, content: t.question },
      { role: "assistant" as const, content: t.answer },
    ]);
    try {
      const res = await run({ message: trimmed, history });
      setTurns((prev) => [
        ...prev,
        {
          id: nextId.current++,
          question: trimmed,
          answer: res.answer,
          citations: res.citations,
          model: res.model,
        },
      ]);
      setDraft("");
    } catch {
      // `error` from useCompassAction is rendered below.
    }
  }

  return (
    <section className="compass-rise flex h-full flex-col rounded-md border border-border bg-surface shadow-soft">
      <header className="flex items-start gap-2.5 border-b border-border px-4 py-3">
        <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded bg-gov-primary text-white">
          <MessageSquareQuote className="size-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className="text-[14.5px] font-semibold text-text-strong">Ask the portfolio</h2>
          <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">
            Retrieval-grounded Q&amp;A over {scopeLabel}. Every answer cites the grants it used.
          </p>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3" aria-live="polite">
        {turns.length === 0 ? (
          <div className="flex flex-col gap-2">
            <p className="text-[11.5px] text-text-subtle">Try one of these:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => void ask(s)}
                disabled={pending}
                className="flex items-start gap-2 rounded border border-border px-3 py-2 text-left text-[12px] text-text transition-colors hover:border-border-strong hover:bg-surface-2 disabled:opacity-50"
              >
                <Sparkles className="mt-[2px] size-3.5 shrink-0 text-gov-secondary" aria-hidden />
                {s}
              </button>
            ))}
          </div>
        ) : (
          <ol className="flex flex-col gap-4">
            {turns.map((t) => (
              <li key={t.id}>
                <p className="text-[12px] font-semibold text-text-strong">{t.question}</p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-text">{t.answer}</p>

                {t.citations.length > 0 ? (
                  <ul className="mt-2.5 flex flex-col gap-1.5">
                    {t.citations.map((c) => (
                      <li
                        key={c.grant_no}
                        className="rounded border border-border-2 bg-surface-2 px-2.5 py-2"
                      >
                        <p className="flex items-center gap-1.5">
                          <Quote className="size-3 shrink-0 text-text-subtle" aria-hidden />
                          <span className="font-mono text-[11px] font-semibold text-gov-primary">
                            {c.grant_no}
                          </span>
                        </p>
                        <p className="mt-0.5 text-[11.5px] font-medium leading-snug text-text-strong">
                          {c.title}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-snug text-text-muted">{c.snippet}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 rounded border border-dashed border-border px-2.5 py-1.5 text-[11px] text-text-subtle">
                    No grants were retrieved for this question — the answer is not grounded in a
                    citation.
                  </p>
                )}

                <p className="mt-1.5 font-mono text-[10px] text-text-subtle">model: {t.model}</p>
              </li>
            ))}
          </ol>
        )}

        {pending ? (
          <p className="mt-3 flex items-center gap-2 text-[11.5px] text-text-muted">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Retrieving grants and generating…
          </p>
        ) : null}

        {error ? (
          <p className="mt-3 rounded border border-danger bg-danger-soft px-2.5 py-2 text-[11.5px] text-danger">
            {error}
          </p>
        ) : null}
      </div>

      <form
        className="border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(draft);
        }}
      >
        <label htmlFor="ask-compass-input" className="sr-only">
          Ask a question about the portfolio
        </label>
        <div className="flex items-end gap-2">
          <textarea
            id="ask-compass-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void ask(draft);
              }
            }}
            rows={2}
            placeholder="e.g. Which program areas grew fastest since FY24?"
            className="min-h-[46px] flex-1 resize-none rounded border border-border bg-surface px-2.5 py-2 text-[12.5px] text-text placeholder:text-text-subtle focus:border-gov-primary focus:outline-none"
          />
          <button
            type="submit"
            disabled={pending || draft.trim().length === 0}
            className="inline-flex h-[38px] shrink-0 items-center gap-1.5 rounded bg-gov-primary px-3 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            Ask
            <CornerDownLeft className="size-3.5" aria-hidden />
          </button>
        </div>
        <p className="mt-2 text-[10.5px] leading-snug text-text-subtle">
          Generation runs in-boundary on Amazon Bedrock; retrieval is limited to rows your role can
          read. Synthetic portfolio — answers are about mock data only.
        </p>
      </form>
    </section>
  );
}

export default AskCompass;
