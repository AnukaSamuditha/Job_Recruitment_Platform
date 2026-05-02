/** Map backend WebSocket JSON events to recruiter-friendly status text. */

type ScreeningEvent = {
  type?: string;
  detail?: string;
};

export function parseScreeningWsPayload(raw: string): ScreeningEvent | null {
  try {
    return JSON.parse(raw) as ScreeningEvent;
  } catch {
    return null;
  }
}

/** Terminal screening events — caller should stop treating the candidate as "in progress". */
export function isScreeningTerminalEvent(raw: string): boolean {
  const p = parseScreeningWsPayload(raw);
  return p?.type === "done" || p?.type === "error";
}

export function friendlyScreeningMessage(raw: string): string | null {
  const parsed = parseScreeningWsPayload(raw);
  if (!parsed) return null;
  const t = parsed.type;
  if (t === "ping") return null;
  if (t === "screening_started") return "Review started.";
  if (t === "parsing") return "Reading CV content…";
  if (t === "matching") return "Comparing skills to the job…";
  if (t === "ranking") return "Ranking fit for this role…";
  if (t === "interview_gen") return "Drafting interview questions…";
  if (t === "parse_issue") {
    const d = parsed.detail != null ? String(parsed.detail) : "";
    return d ? `CV parsing: ${d}` : "CV structured parsing reported an issue.";
  }
  if (t === "done") return "Analysis complete.";
  if (t === "error") return "Something went wrong during analysis. Try uploading again.";
  if (parsed.detail) return String(parsed.detail);
  return null;
}
