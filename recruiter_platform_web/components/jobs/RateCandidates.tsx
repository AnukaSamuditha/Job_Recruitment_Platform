"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { UploadCloud, Trash2, Eye, Loader2 } from "lucide-react";
import CandidateDetail from "@/components/candidates/CandidateDetail";
import { apiWsBase } from "@/lib/api/config";
import {
  friendlyScreeningMessage,
  isScreeningTerminalEvent,
  parseScreeningWsPayload,
} from "@/lib/screeningMessages";
import {
  listJobCandidates,
  uploadCandidateCvWithProgress,
  type ApiCandidate,
} from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Row = {
  id: string;
  name: string;
  email: string;
  score: number;
  status: "analyzing" | "complete";
};

function shortFileLabel(name: string): string {
  return name.length > 28 ? `${name.slice(0, 14)}…${name.slice(-10)}` : name;
}

export default function RateCandidates({ jobId }: { jobId: string }) {
  const [apiRows, setApiRows] = useState<ApiCandidate[]>([]);
  const [analyzingIds, setAnalyzingIds] = useState<Set<string>>(() => new Set());
  const [selected, setSelected] = useState<Row | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  /** Bytes upload progress for the file currently being sent */
  const [uploadProgress, setUploadProgress] = useState<{
    fileName: string;
    percent: number;
    indeterminate: boolean;
  } | null>(null);
  /** Live timeline from WebSocket(s) — multiple uploads can stream in parallel */
  const [activityLines, setActivityLines] = useState<string[]>([]);

  const socketsRef = useRef<Map<string, WebSocket>>(new Map());
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadBusyRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!jobId || jobId === "unknown") return;
    try {
      const rows = await listJobCandidates(jobId);
      setApiRows(rows);
    } catch {
      setApiRows([]);
    }
  }, [jobId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    return () => {
      for (const ws of socketsRef.current.values()) {
        ws.close();
      }
      socketsRef.current.clear();
    };
  }, []);

  const candidates: Row[] = useMemo(
    () =>
      apiRows.map((c) => ({
        id: c.id,
        name: c.display_name,
        email: "—",
        score: typeof c.match_score === "number" ? c.match_score : 0,
        status: analyzingIds.has(c.id) ? ("analyzing" as const) : ("complete" as const),
      })),
    [apiRows, analyzingIds],
  );

  const openScreeningSocket = useCallback(
    (runId: string, candidateId: string, fileLabel: string) => {
      if (!runId || socketsRef.current.has(runId)) return;

      const prefix = shortFileLabel(fileLabel);
      const append = (msg: string) => {
        setActivityLines((lines) => [...lines.slice(-60), `[${prefix}] ${msg}`]);
      };

      const wsUrl = `${apiWsBase()}/api/v1/ws/screening/${runId}`;
      const ws = new WebSocket(wsUrl);
      socketsRef.current.set(runId, ws);

      ws.onopen = () => {
        append("Connected — receiving live screening updates.");
        // #region agent log
        fetch("http://127.0.0.1:7925/ingest/a4a8d503-3acb-41c9-ad31-b49e964e236e", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "2354bc" },
          body: JSON.stringify({
            sessionId: "2354bc",
            hypothesisId: "H1",
            location: "RateCandidates.tsx:ws.onopen",
            message: "screening_ws_open",
            data: { wsUrlLen: wsUrl.length, wsHost: (() => { try { return new URL(wsUrl).host; } catch { return ""; } })() },
            timestamp: Date.now(),
          }),
        }).catch(() => {});
        // #endregion
      };

      ws.onmessage = (ev) => {
        const raw = ev.data as string;
        if (isScreeningTerminalEvent(raw)) {
          const human = friendlyScreeningMessage(raw) ?? "Update finished.";
          append(human);
          const parsed = parseScreeningWsPayload(raw);
          setAnalyzingIds((prev) => {
            const next = new Set(prev);
            next.delete(candidateId);
            return next;
          });
          void refresh();
          if (parsed?.type === "done" || parsed?.type === "error") {
            ws.close();
          }
          return;
        }
        const line = friendlyScreeningMessage(raw);
        if (line) append(line);
      };

      ws.onerror = () => {
        // #region agent log
        fetch("http://127.0.0.1:7925/ingest/a4a8d503-3acb-41c9-ad31-b49e964e236e", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "2354bc" },
          body: JSON.stringify({
            sessionId: "2354bc",
            hypothesisId: "H1",
            location: "RateCandidates.tsx:ws.onerror",
            message: "screening_ws_error",
            data: {
              runIdPrefix: runId.slice(0, 8),
              wsHost: (() => {
                try {
                  return new URL(wsUrl).host;
                } catch {
                  return "";
                }
              })(),
            },
            timestamp: Date.now(),
          }),
        }).catch(() => {});
        // #endregion
        append("Connection issue — the file was saved; refresh if status looks stuck.");
        setAnalyzingIds((prev) => {
          const next = new Set(prev);
          next.delete(candidateId);
          return next;
        });
        void refresh();
      };

      ws.onclose = () => {
        socketsRef.current.delete(runId);
        setAnalyzingIds((prev) => {
          const next = new Set(prev);
          next.delete(candidateId);
          return next;
        });
        void refresh();
      };
    },
    [refresh],
  );

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0 || !jobId || jobId === "unknown") return;
    if (uploadBusyRef.current) return;
    uploadBusyRef.current = true;
    setUploadError(null);
    setActivityLines((lines) => [...lines, `Starting upload (${files.length} file(s))…`]);

    try {
      for (const f of Array.from(files)) {
        if (!f.name.toLowerCase().endsWith(".pdf")) {
          setUploadError(`Only PDF files are supported. Skipped: ${f.name}`);
          continue;
        }

        setUploadProgress({
          fileName: f.name,
          percent: 0,
          indeterminate: true,
        });

        const displayName = f.name.replace(/\.[^/.]+$/, "");
        const res = await uploadCandidateCvWithProgress(jobId, f, {
          displayName,
          onProgress: ({ percent, total }) => {
            setUploadProgress({
              fileName: f.name,
              percent,
              indeterminate: total == null,
            });
          },
        });

        setUploadProgress(null);

        setAnalyzingIds((prev) => new Set(prev).add(res.candidate_id));
        await refresh();

        setActivityLines((lines) => [
          ...lines.slice(-60),
          `[${shortFileLabel(f.name)}] File received — evaluation running in the background.`,
        ]);

        if (res.screening_run_id) {
          openScreeningSocket(res.screening_run_id, res.candidate_id, f.name);
        } else {
          setActivityLines((lines) => [
            ...lines.slice(-60),
            `[${shortFileLabel(f.name)}] No live run id returned — refresh to see updates.`,
          ]);
          setAnalyzingIds((prev) => {
            const next = new Set(prev);
            next.delete(res.candidate_id);
            return next;
          });
        }
      }
    } catch (e) {
      setUploadError("Upload failed. Check your connection and try again.");
      console.error(e);
      setUploadProgress(null);
    }
  }

  function removeCandidate(id: string) {
    setApiRows((rows) => rows.filter((c) => c.id !== id));
    setAnalyzingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  const completeCount = candidates.filter((c) => c.status === "complete").length;
  const analyzingCount = candidates.filter((c) => c.status === "analyzing").length;
  const averageScore = completeCount
    ? Math.round(
        candidates.filter((c) => c.status === "complete").reduce((sum, c) => sum + c.score, 0) /
          completeCount,
      )
    : 0;

  const showEvaluationPanel =
    uploadProgress != null || analyzingCount > 0 || activityLines.length > 0;

  const sortedCandidates = useMemo(() => {
    return candidates.slice().sort((a, b) => {
      if (a.status === "analyzing" && b.status !== "analyzing") return -1;
      if (a.status !== "analyzing" && b.status === "analyzing") return 1;
      return b.score - a.score;
    });
  }, [candidates]);

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle>Candidate CVs</CardTitle>
              <CardDescription>
                Upload a PDF résumé. You will see send progress, then each new row stays in Evaluating until the
                automated review finishes and live status updates appear below.
              </CardDescription>
            </div>
            <Badge variant="outline" className="shrink-0 font-mono text-xs font-normal">
              {jobId.length > 14 ? `${jobId.slice(0, 8)}…` : jobId}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex cursor-pointer flex-col gap-3 rounded-lg border border-dashed border-border/80 bg-muted/30 px-4 py-6 transition-colors hover:border-[var(--accent)]/40 hover:bg-muted/50 sm:flex-row sm:items-center sm:justify-between">
              <input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                multiple
                accept=".pdf,application/pdf"
                onChange={(e) => void handleUpload(e.target.files)}
              />
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)]/12">
                  <UploadCloud className="h-5 w-5 text-[var(--accent)]" aria-hidden />
                </div>
                <div>
                  <p className="font-medium text-foreground">Drop PDFs here or browse</p>
                  <p className="text-sm text-muted-foreground">One or more PDF files</p>
                </div>
              </div>
              <Button type="button" variant="secondary" size="sm" className="pointer-events-none sm:pointer-events-auto">
                Choose files
              </Button>
            </label>

            {uploadProgress && (
              <div className="space-y-2 rounded-lg border border-border/60 bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span className="truncate font-medium text-foreground">Sending {shortFileLabel(uploadProgress.fileName)}</span>
                  {!uploadProgress.indeterminate && <span>{uploadProgress.percent}%</span>}
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={uploadProgress.percent} aria-valuemin={0} aria-valuemax={100}>
                  {uploadProgress.indeterminate ? (
                    <div className="h-full w-1/3 animate-pulse rounded-full bg-[var(--accent)]" />
                  ) : (
                    <div
                      className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-150"
                      style={{ width: `${uploadProgress.percent}%` }}
                    />
                  )}
                </div>
              </div>
            )}

            {analyzingCount > 0 && !uploadProgress && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--accent)]" aria-hidden />
                <span>
                  Evaluating {analyzingCount} candidate{analyzingCount === 1 ? "" : "s"}… (live updates below)
                </span>
              </div>
            )}

            {uploadError && <p className="text-sm text-destructive">{uploadError}</p>}
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Candidates</CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums">{candidates.length}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Average match score</CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums text-[var(--accent)]">{averageScore}%</CardTitle>
            </CardHeader>
          </Card>
        </div>
      </div>

      {showEvaluationPanel && (
        <Card className="border-border/80 border-[var(--accent)]/25">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Evaluation activity</CardTitle>
            <CardDescription>Upload progress and each screening step as the server runs them.</CardDescription>
          </CardHeader>
          <CardContent>
            {activityLines.length === 0 && uploadProgress == null && analyzingCount === 0 ? (
              <p className="text-sm text-muted-foreground">Waiting for activity…</p>
            ) : (
              <ul className="max-h-64 space-y-2 overflow-y-auto text-sm text-muted-foreground">
                {activityLines.map((line, i) => (
                  <li key={`${i}-${line.slice(0, 48)}`} className="flex gap-2 border-b border-border/40 pb-2 last:border-0">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" aria-hidden />
                    <span className="leading-relaxed">{line}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
          <div>
            <CardTitle className="text-base">Shortlist</CardTitle>
            <CardDescription>
              {analyzingCount > 0
                ? `${completeCount} ready · ${analyzingCount} evaluating`
                : "Review uploaded applicants for this job."}
            </CardDescription>
          </div>
          <Badge variant="secondary">{candidates.length} total</Badge>
        </CardHeader>
        <CardContent>
          <div className="overflow-hidden rounded-lg border border-border/70">
            <table className="w-full table-auto text-sm">
              <thead className="bg-muted/50 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">CV</th>
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {sortedCandidates.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                      No candidates yet. Upload a PDF to get started.
                    </td>
                  </tr>
                ) : (
                  sortedCandidates.map((c) => (
                    <tr key={c.id} className="bg-card transition-colors hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">
                        <div className="flex items-center gap-2">
                          {c.status === "analyzing" && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-[var(--accent)]" aria-hidden />}
                          {c.name}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{c.email}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {c.status === "analyzing" ? (
                          <span className="inline-flex items-center gap-1 text-[var(--accent)]">
                            Evaluating…
                          </span>
                        ) : (
                          "Ready"
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {c.status === "analyzing" ? (
                          <Badge variant="outline" className="gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                            In progress
                          </Badge>
                        ) : (
                          <Badge variant="accent">{c.score > 0 ? `${c.score}%` : "—"}</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="icon-sm"
                            onClick={() => setSelected(c)}
                            aria-label={`View ${c.name}`}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon-sm"
                            className="text-destructive hover:bg-destructive/10"
                            onClick={() => removeCandidate(c.id)}
                            aria-label={`Remove ${c.name} from list`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {selected && (
        <CandidateDetail jobId={jobId} candidate={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
