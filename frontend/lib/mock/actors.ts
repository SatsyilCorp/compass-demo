import type { Role } from "@/lib/types";


/** Stable synthetic people used to make replay separation of duties visible. */
export const REPLAY_ACTORS: Record<Role, string> = {
  viewer: "Maya Chen | Code-30 requester",
  poweruser: "Eli Brooks | ONR reviewer",
};

export function replayActor(role: Role | null | undefined): string {
  return REPLAY_ACTORS[role ?? "viewer"];
}
