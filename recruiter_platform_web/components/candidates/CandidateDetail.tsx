"use client";

import React, { useEffect, useMemo, useState } from "react";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  getCandidateCvPreview,
  getCandidateDetail,
  type CandidateDetail as CandidateDetailApi,
  type CandidateJobScreening,
} from "@/lib/api/jobs";

export type CandidateDetailRow = {
  id: string;
  name: string;
  email: string;
  score: number;
};

function strVal(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

/** True if structured JSON has any non-empty field we would show (not only default empty strings). */
function profileHasMeaningfulData(profile: Record<string, unknown> | null): boolean {
  if (!profile) return false;
  if (strVal(profile.full_name).trim()) return true;
  if (strVal(profile.headline).trim()) return true;
  if (strVal(profile.summary).trim()) return true;
  if (strVal(profile.email).trim() || strVal(profile.phone).trim() || strVal(profile.location).trim()) return true;
  const skills = Array.isArray(profile.skills) ? profile.skills : [];
  if (skills.some((s) => typeof s === "string" && s.trim())) return true;
  const work = Array.isArray(profile.work_experience) ? profile.work_experience : [];
  for (const w of work) {
    if (!w || typeof w !== "object") continue;
    const row = w as Record<string, unknown>;
    if (
      strVal(row.company).trim() ||
      strVal(row.job_title).trim() ||
      (Array.isArray(row.highlights) && row.highlights.some((h) => typeof h === "string" && h.trim()))
    ) {
      return true;
    }
  }
  const edu = Array.isArray(profile.education) ? profile.education : [];
  for (const e of edu) {
    if (!e || typeof e !== "object") continue;
    const row = e as Record<string, unknown>;
    if (strVal(row.institution).trim() || strVal(row.degree).trim()) return true;
  }
  return false;
}

function jobScreeningToSnippets(js: CandidateJobScreening | undefined): Record<string, string> | null {
  if (!js) return null;
  const o: Record<string, string> = {};
  if (js.skill_match?.trim()) o.skill_match = js.skill_match.trim();
  if (js.ranking?.trim()) o.ranking = js.ranking.trim();
  if (js.interview?.trim()) o.interview = js.interview.trim();
  return Object.keys(o).length ? o : null;
}

/** Turn model output into short lines for the interview panel. */
function splitInterviewLines(text: string): string[] {
  return text
    .split(/\n+/)
    .map((l) => l.replace(/^\s*(\d+[\).\]]|[•\-*]|\(?[a-z]\))\s+/iu, "").trim())
    .filter((l) => l.length > 3);
}

function ProfileBody({ profile }: { profile: Record<string, unknown> }) {
  const fullName = strVal(profile.full_name);
  const email = strVal(profile.email);
  const phone = strVal(profile.phone);
  const location = strVal(profile.location);
  const headline = strVal(profile.headline);
  const summary = strVal(profile.summary);
  const skills = Array.isArray(profile.skills) ? profile.skills.filter((s) => typeof s === "string" && s.trim()) : [];
  const work = Array.isArray(profile.work_experience) ? profile.work_experience : [];
  const education = Array.isArray(profile.education) ? profile.education : [];

  return (
    <div className="space-y-5 text-sm">
      {(fullName || headline || location) && (
        <div>
          {fullName && <p className="text-lg font-semibold text-foreground">{fullName}</p>}
          {headline && <p className="mt-1 text-muted-foreground">{headline}</p>}
          {(email || phone || location) && (
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              {[email, phone, location].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
      )}
      {summary && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Summary</p>
          <p className="mt-1 whitespace-pre-wrap text-foreground/90">{summary}</p>
        </div>
      )}
      {skills.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Skills on the CV</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {skills.slice(0, 48).map((s, idx) => (
              <Badge key={`${s}-${idx}`} variant="secondary" className="font-normal">
                {s}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {work.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Experience</p>
          <ul className="mt-2 space-y-3">
            {work.slice(0, 10).map((w, i) => {
              const row = w as Record<string, unknown>;
              const title = strVal(row.job_title);
              const company = strVal(row.company);
              const dates = [strVal(row.start_date), strVal(row.end_date)].filter(Boolean).join(" – ");
              const highlights = Array.isArray(row.highlights)
                ? row.highlights.filter((h) => typeof h === "string" && h.trim())
                : [];
              return (
                <li key={i} className="rounded-md border border-border/50 bg-muted/20 p-3">
                  <p className="font-medium text-foreground">
                    {title || "Role"}
                    {company ? <span className="font-normal text-muted-foreground"> · {company}</span> : null}
                  </p>
                  {dates && <p className="mt-0.5 text-xs text-muted-foreground">{dates}</p>}
                  {highlights.length > 0 && (
                    <ul className="mt-2 list-inside list-disc text-xs text-muted-foreground">
                      {highlights.slice(0, 6).map((h, j) => (
                        <li key={j}>{h}</li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {education.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Education</p>
          <ul className="mt-2 space-y-2 text-xs text-muted-foreground">
            {education.slice(0, 6).map((e, i) => {
              const row = e as Record<string, unknown>;
              return (
                <li key={i}>
                  {strVal(row.degree)} {strVal(row.field_of_study)} — {strVal(row.institution)}
                  {strVal(row.end_date) ? ` (${strVal(row.end_date)})` : ""}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function CandidateDetail({
  jobId,
  candidate,
  onClose,
}: {
  jobId: string;
  candidate: CandidateDetailRow;
  onClose: () => void;
}) {
  const [pages, setPages] = useState<string[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [detail, setDetail] = useState<CandidateDetailApi | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [previewExtras, setPreviewExtras] = useState<{
    summary_text: string | null;
    structured_profile: Record<string, unknown> | null;
    screening: Record<string, string> | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [interviewPanelOpen, setInterviewPanelOpen] = useState(false);

  useEffect(() => {
    if (!jobId || jobId === "unknown" || !candidate.id) {
      setLoading(false);
      setFatalError("Missing job or candidate.");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setFatalError(null);
    setPreviewError(null);
    setDetailError(null);
    setPages([]);
    setDetail(null);
    setPreviewExtras(null);
    setInterviewPanelOpen(false);
    void (async () => {
      const previewP = getCandidateCvPreview(jobId, candidate.id);
      const detailP = getCandidateDetail(jobId, candidate.id);
      const [pRes, dRes] = await Promise.allSettled([previewP, detailP]);
      if (cancelled) return;
      if (pRes.status === "fulfilled") {
        setPages(pRes.value.pages ?? []);
        setPreviewExtras({
          summary_text: pRes.value.summary_text ?? null,
          structured_profile: pRes.value.structured_profile ?? null,
          screening: pRes.value.screening ?? null,
        });
        setPreviewError(null);
      } else {
        setPages([]);
        setPreviewExtras(null);
        const msg =
          pRes.reason instanceof Error ? pRes.reason.message : "Could not load résumé preview.";
        setPreviewError(msg);
      }
      if (dRes.status === "fulfilled") {
        setDetail(dRes.value);
        setDetailError(null);
      } else {
        setDetail(null);
        const msg =
          dRes.reason instanceof Error ? dRes.reason.message : "Could not load candidate profile.";
        setDetailError(msg);
      }
      if (pRes.status === "rejected" && dRes.status === "rejected") {
        setFatalError(
          dRes.reason instanceof Error ? dRes.reason.message : "Could not load candidate data.",
        );
      } else {
        setFatalError(null);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId, candidate.id]);

  const structuredProfile = useMemo(() => {
    if (detail?.structured_profile) return detail.structured_profile;
    return previewExtras?.structured_profile ?? null;
  }, [detail, previewExtras]);

  const summaryText = useMemo(() => {
    if (detail?.parse_summary) return detail.parse_summary;
    return previewExtras?.summary_text ?? null;
  }, [detail, previewExtras]);

  const screening = useMemo(() => {
    const fromDetail = jobScreeningToSnippets(detail?.job_screening);
    if (fromDetail) return fromDetail;
    return previewExtras?.screening ?? null;
  }, [detail, previewExtras]);

  const headerEmail = useMemo(() => {
    const fromContact = detail?.contact?.email?.trim();
    if (fromContact) return fromContact;
    const fromProfile = structuredProfile && strVal(structuredProfile.email);
    if (fromProfile) return fromProfile;
    return candidate.email;
  }, [detail?.contact?.email, structuredProfile, candidate.email]);

  const headerName = useMemo(() => {
    const fromContact = detail?.contact?.full_name?.trim();
    if (fromContact) return fromContact;
    const fromProfile = structuredProfile && strVal(structuredProfile.full_name).trim();
    if (fromProfile) return fromProfile;
    return candidate.name;
  }, [detail?.contact?.full_name, structuredProfile, candidate.name]);

  const contactLine = useMemo(() => {
    const c = detail?.contact;
    if (!c) return null;
    const parts = [c.phone?.trim(), c.location?.trim()].filter(Boolean);
    return parts.length ? parts.join(" · ") : null;
  }, [detail?.contact]);

  const jobFitScore = detail?.job_fit?.overall_score;
  const missingSkills = detail?.job_fit?.missing_skills ?? [];
  const jobFitSummary = detail?.job_fit?.summary_line?.trim() ?? "";

  const interviewRaw = screening?.interview?.trim() ?? "";

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden />
      <div className="relative z-10 flex h-full min-h-0 flex-1 flex-col shadow-[0_0_40px_rgba(0,0,0,0.12)]">
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border/70 bg-card px-4 py-4 sm:px-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Candidate</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">{headerName}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{headerEmail}</p>
            {contactLine ? (
              <p className="mt-0.5 text-xs text-muted-foreground">{contactLine}</p>
            ) : null}
          </div>
          <Button type="button" variant="outline" size="icon" aria-label="Close" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          {/* CV pages */}
          <section
            aria-label="CV preview"
            className="flex min-h-[40vh] min-w-0 flex-col border-border/70 bg-muted/25 lg:min-h-0 lg:w-1/2 lg:max-w-[55%] lg:border-r"
          >
            <div className="shrink-0 border-b border-border/50 bg-muted/40 px-4 py-3 sm:px-6">
              <h3 className="text-sm font-semibold text-foreground">Résumé</h3>
              <p className="text-xs text-muted-foreground">Uploaded document</p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
              {loading ? (
                <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                  <Loader2 className="h-8 w-8 animate-spin text-[var(--accent)]" aria-hidden />
                  <span>Loading preview…</span>
                </div>
              ) : fatalError ? (
                <div className="flex min-h-[160px] items-center justify-center rounded-lg border border-dashed border-destructive/40 p-4 text-center text-sm text-destructive">
                  {fatalError}
                </div>
              ) : previewError && pages.length === 0 ? (
                <div className="flex min-h-[160px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-destructive/40 p-4 text-center text-sm text-destructive">
                  <span>{previewError}</span>
                  <span className="text-xs text-muted-foreground">Profile data may still load on the right.</span>
                </div>
              ) : pages.length > 0 ? (
                <div className="space-y-4">
                  {pages.map((src, index) => (
                    <div
                      key={`${candidate.id}-page-${index}`}
                      className="overflow-hidden rounded-lg border border-border/60 bg-card shadow-sm"
                    >
                      <img
                        src={src}
                        alt={`Résumé page ${index + 1}`}
                        className="w-full object-contain"
                        loading="lazy"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex min-h-[160px] items-center justify-center rounded-lg border border-dashed border-border/70 text-center text-sm text-muted-foreground">
                  No preview available for this file.
                </div>
              )}
            </div>
          </section>

          {/* Insights */}
          <section
            aria-label="Candidate overview"
            className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card lg:max-w-[50%]"
          >
            <div className="shrink-0 border-b border-border/50 px-4 py-3 sm:px-6">
              <h3 className="text-sm font-semibold text-foreground">At a glance</h3>
              <p className="text-xs text-muted-foreground">
                Contact, quick take, CV detail — then match score and missing technical skills
              </p>
            </div>

            <div className="relative min-h-0 flex-1 overflow-hidden">
              <div className="h-full overflow-y-auto p-4 sm:p-6">
                <div className="space-y-4">
                  {detailError ? (
                    <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
                      Profile API unavailable ({detailError}). Showing whatever the preview endpoint returned.
                    </p>
                  ) : null}

                  {detail &&
                  (detail.contact.email ||
                    detail.contact.phone ||
                    detail.contact.location ||
                    detail.contact.headline) ? (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">How to reach them</CardTitle>
                        <CardDescription>From the résumé when we could read it clearly.</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-1 text-sm text-muted-foreground">
                        {detail.contact.headline ? (
                          <p className="text-foreground/90">{detail.contact.headline}</p>
                        ) : null}
                        <dl className="grid gap-1 text-xs sm:grid-cols-2">
                          {detail.contact.email ? (
                            <>
                              <dt className="font-medium text-muted-foreground">Email</dt>
                              <dd className="text-foreground">{detail.contact.email}</dd>
                            </>
                          ) : null}
                          {detail.contact.phone ? (
                            <>
                              <dt className="font-medium text-muted-foreground">Phone</dt>
                              <dd className="text-foreground">{detail.contact.phone}</dd>
                            </>
                          ) : null}
                          {detail.contact.location ? (
                            <>
                              <dt className="font-medium text-muted-foreground">Location</dt>
                              <dd className="text-foreground">{detail.contact.location}</dd>
                            </>
                          ) : null}
                        </dl>
                      </CardContent>
                    </Card>
                  ) : null}

                  {detail?.cv_parser_agent ? (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Quick take for this role</CardTitle>
                        <CardDescription>
                          Short, plain-language pointers from your assistant after reading the CV and job posting — use
                          with your own judgment, not as a hire/no-hire verdict.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-5 text-sm">
                        {detail.cv_parser_agent.error ? (
                          <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
                            We couldn&apos;t finish these notes: {detail.cv_parser_agent.error}
                          </p>
                        ) : null}

                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Job alignment
                          </h4>
                          {detail.cv_parser_agent.alignment_summary.length > 0 ? (
                            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-foreground/90">
                              {detail.cv_parser_agent.alignment_summary.map((line, i) => (
                                <li key={i} className="leading-relaxed">
                                  {line}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-xs text-muted-foreground">No alignment bullets returned.</p>
                          )}
                        </div>

                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Interview follow-ups
                          </h4>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Suggested neutral questions for the hiring manager — not accusations.
                          </p>
                          {detail.cv_parser_agent.gaps_or_questions.length > 0 ? (
                            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-foreground/90">
                              {detail.cv_parser_agent.gaps_or_questions.map((line, i) => (
                                <li key={i} className="leading-relaxed">
                                  {line}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-xs text-muted-foreground">No follow-up items returned.</p>
                          )}
                        </div>

                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Process checks
                          </h4>
                          {detail.cv_parser_agent.risk_flags.length > 0 ? (
                            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-foreground/90">
                              {detail.cv_parser_agent.risk_flags.map((line, i) => (
                                <li key={i} className="leading-relaxed">
                                  {line}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-2 text-xs text-muted-foreground">
                              None flagged from CV dates or timeline in the structured data.
                            </p>
                          )}
                        </div>

                        <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-muted-foreground">
                          {detail.cv_parser_agent.disclaimer}
                        </p>
                      </CardContent>
                    </Card>
                  ) : null}

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">What we read from the CV</CardTitle>
                      <CardDescription>Structured fields when extraction succeeds.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {loading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" aria-hidden />
                          Loading…
                        </div>
                      ) : profileHasMeaningfulData(structuredProfile) ? (
                        <ProfileBody profile={structuredProfile!} />
                      ) : structuredProfile && Object.keys(structuredProfile).length > 0 ? (
                        <div className="space-y-3">
                          <p className="text-sm text-muted-foreground">
                            Structured extraction ran but every field is empty. The CV layout may be unclear to the
                            parser, or LlamaCloud returned an empty object.
                          </p>
                          {summaryText && (
                            <div>
                              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                Plain-text summary
                              </p>
                              <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-md border border-border/50 bg-muted/30 p-3 font-sans text-xs leading-relaxed">
                                {summaryText}
                              </pre>
                            </div>
                          )}
                        </div>
                      ) : summaryText ? (
                        <div>
                          <p className="mb-2 text-sm text-muted-foreground">
                            No filled structured JSON yet; below is the text summary stored for agents.
                          </p>
                          <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-border/50 bg-muted/30 p-3 font-sans text-xs leading-relaxed">
                            {summaryText}
                          </pre>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No structured data yet. It appears when LlamaParse structured extraction succeeds during
                          screening (check the activity feed for parse issues). After a successful run, reopen this
                          panel or refresh the shortlist—the name column updates from the extracted full name.
                        </p>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardDescription>Fit with this job posting</CardDescription>
                      <CardTitle className="text-3xl font-semibold text-[var(--accent)] tabular-nums">
                        {typeof jobFitScore === "number"
                          ? `${jobFitScore}%`
                          : candidate.score > 0
                            ? `${candidate.score}%`
                            : "—"}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm text-muted-foreground">
                        {jobFitSummary ||
                          "After screening runs, we compare important words in the job description with the CV. Re-run screening to refresh this score."}
                      </p>
                      {typeof jobFitScore !== "number" && candidate.score > 0 ? (
                        <p className="text-xs text-muted-foreground">Shortlist table score (legacy): {candidate.score}%</p>
                      ) : null}
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="w-full sm:w-auto"
                        onClick={() => setInterviewPanelOpen(true)}
                      >
                        Preview interview questions
                      </Button>
                    </CardContent>
                  </Card>

                  {missingSkills.length > 0 ? (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Missing technical skills</CardTitle>
                        <CardDescription>
                          Tools, stacks, or technical terms called out in the job description that we did not clearly
                          find on this CV (automatic match — always double-check).
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex flex-wrap gap-1.5">
                          {missingSkills.map((s, idx) => (
                            <Badge
                              key={`miss-${s}-${idx}`}
                              variant="outline"
                              className="font-normal border-amber-500/50 text-amber-950 dark:text-amber-100"
                            >
                              {s}
                            </Badge>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ) : detail?.job_fit != null ? (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Missing technical skills</CardTitle>
                        <CardDescription>
                          No obvious technical gaps vs the job posting after the last screening run, or the job text
                          had little we could match as technical skills.
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  ) : null}
                </div>
              </div>

              {/* Interview questions slide-over (right column only) */}
              {interviewPanelOpen ? (
                <div
                  className="absolute inset-0 z-30 flex flex-col border-l border-border bg-card shadow-xl"
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="interview-panel-title"
                >
                  <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/60 px-4 py-3 sm:px-6">
                    <div>
                      <h3 id="interview-panel-title" className="text-sm font-semibold text-foreground">
                        Interview questions
                      </h3>
                      <p className="text-xs text-muted-foreground">Latest screening pass for this job</p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setInterviewPanelOpen(false)}
                    >
                      Close
                    </Button>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
                    {interviewRaw ? (
                      <>
                        {(() => {
                          const lines = splitInterviewLines(interviewRaw);
                          return lines.length > 0 ? (
                            <ol className="list-decimal space-y-3 pl-4 text-sm text-foreground/90">
                              {lines.map((line, i) => (
                                <li key={i} className="leading-relaxed">
                                  {line}
                                </li>
                              ))}
                            </ol>
                          ) : (
                            <pre className="max-h-[min(70vh,32rem)] overflow-auto whitespace-pre-wrap rounded-md border border-border/40 bg-muted/20 p-3 font-sans text-sm leading-relaxed">
                              {interviewRaw}
                            </pre>
                          );
                        })()}
                        <details className="mt-6">
                          <summary className="cursor-pointer text-xs text-muted-foreground">Raw model output</summary>
                          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-border/40 bg-muted/20 p-3 font-sans text-xs leading-relaxed text-muted-foreground">
                            {interviewRaw}
                          </pre>
                        </details>
                      </>
                    ) : (
                      <div className="space-y-2 text-sm text-muted-foreground">
                        <p>
                          No interview questions are stored for this job yet. Run <strong>screening</strong> for this
                          job and wait until the pipeline finishes — questions are generated in the final interview
                          step from the skill match and ranking summaries.
                        </p>
                        <p className="text-xs">
                          If screening completes but this stays empty, check that Ollama is running and
                          <code className="mx-1 rounded bg-muted px-1">OLLAMA_CHAT_MODEL</code> is pulled on the API
                          server.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
