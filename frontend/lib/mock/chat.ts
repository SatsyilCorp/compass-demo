/**
 * POST /chat — fixture. Element 6 (NL Q&A, RAG over curated grants via
 * Bedrock in the deployed system). Canned but grounded in the same
 * synthetic portfolio the rest of the mock data uses, with real citations
 * into it — not a generic chatbot echo.
 */
import type { ChatCitation, ChatRequest, ChatResponse, Role } from "@/lib/types";
import { visibleGrants } from "./grants";

export function answerChat(req: ChatRequest, role: Role | null, orgUnit: string | null): ChatResponse {
  const visible = visibleGrants(role, orgUnit);
  const q = req.message.toLowerCase();
  const matches = visible.filter(
    (g) =>
      q.split(/\s+/).some((word) => word.length > 3 && (g.title.toLowerCase().includes(word) || g.program_area.toLowerCase().includes(word))),
  );
  const top = (matches.length > 0 ? matches : visible).slice(0, 3);
  const citations: ChatCitation[] = top.map((g) => ({
    grant_no: g.grant_no,
    title: g.title,
    snippet: g.abstract.slice(0, 160) + (g.abstract.length > 160 ? "…" : ""),
  }));

  const answer =
    top.length > 0
      ? `Based on ${top.length} matching grant${top.length === 1 ? "" : "s"} in the portfolio visible to your role, ${top[0]!.program_area} is the most relevant area — see "${top[0]!.title}" (${top[0]!.grant_no}). ${
          role === "viewer" ? "Note: award amounts are masked for the viewer role per column-level security." : ""
        }`.trim()
      : "No grants in your visible portfolio match that question. Try asking about a program area (e.g. Autonomous Systems, Undersea Warfare, Directed Energy).";

  return { answer, citations, model: "amazon.nova-lite-v1:0 (mock)" };
}
