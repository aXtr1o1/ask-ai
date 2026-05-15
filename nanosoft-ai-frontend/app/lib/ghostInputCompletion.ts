import { LANDING_SUGGESTED_QUERY_GROUPS } from "../components/LandingSuggestedQueries";

/** Minimal message shape used to build ghost completion candidates. */
export type GhostCompletionMessage = {
  role: "user" | "ai" | "error";
  text: string;
  isAudio?: boolean;
};

function flattenLandingGhostQueries(): string[] {
  const out: string[] = [];
  for (const g of LANDING_SUGGESTED_QUERY_GROUPS) {
    for (const q of g.queries) {
      const t = q.trim();
      if (t.length >= 2) out.push(t);
    }
  }
  return out;
}

const LANDING_GHOST_QUERIES = flattenLandingGhostQueries();

const GHOST_PROMPT_HISTORY_PREFIX = "askAiGhostPromptHistory:";
const GHOST_PROMPT_HISTORY_MAX = 150;

export function ghostPromptHistoryStorageKey(loggedInUser: string | null): string {
  const u = loggedInUser?.trim();
  return `${GHOST_PROMPT_HISTORY_PREFIX}${u && u.length > 0 ? u : "anon"}`;
}

function readStoredGhostPrompts(storageKey: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((s): s is string => typeof s === "string" && s.trim().length >= 2)
      .map((s) => s.trim());
  } catch {
    return [];
  }
}

export function recordPromptForGhostHistory(storageKey: string, text: string): void {
  if (typeof window === "undefined") return;
  const t = text.trim();
  if (t.length < 2) return;
  try {
    const prev = readStoredGhostPrompts(storageKey);
    const next = [t, ...prev.filter((x) => x.toLowerCase() !== t.toLowerCase())].slice(0, GHOST_PROMPT_HISTORY_MAX);
    localStorage.setItem(storageKey, JSON.stringify(next));
  } catch {
    /* ignore quota / private mode */
  }
}

export function pickInlineGhostSuffix(query: string, candidates: string[]): string {
  if (!query) return "";
  const lower = query.toLowerCase();
  let best = "";
  for (const c of candidates) {
    if (c.length <= query.length) continue;
    if (!c.toLowerCase().startsWith(lower)) continue;
    const suffix = c.slice(query.length);
    if (suffix.length > best.length) best = suffix;
  }
  return best;
}

export function buildGhostCandidates(messages: GhostCompletionMessage[], ghostHistoryKey: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (t: string) => {
    const norm = t.toLowerCase();
    if (seen.has(norm)) return;
    seen.add(norm);
    out.push(t);
  };
  for (const t of LANDING_GHOST_QUERIES) push(t);
  for (const t of readStoredGhostPrompts(ghostHistoryKey)) push(t);
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== "user" || m.isAudio) continue;
    const text = m.text?.trim();
    if (!text || text.length < 2) continue;
    push(text);
    if (out.length > 250) break;
  }
  return out;
}
