"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import { Loader2, Trophy, ListOrdered, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiWsBase } from "@/lib/api/config";
import {
  friendlyScreeningMessage,
  isScreeningTerminalEvent,
} from "@/lib/screeningMessages";
import {
  getJobScreening,
  rankCandidates,
  type CandidateJobScreening,
} from "@/lib/api/jobs";

export default function JobRanking({ jobId }: { jobId: string }) {
  const [screening, setScreening] = useState<CandidateJobScreening | null>(null);
  const [isRanking, setIsRanking] = useState(false);
  const [activityLines, setActivityLines] = useState<string[]>([]);
  const socketsRef = useRef<Map<string, WebSocket>>(new Map());

  const refresh = useCallback(async () => {
    if (!jobId || jobId === "unknown") return;
    try {
      const data = await getJobScreening(jobId);
      setScreening(data);
    } catch (e) {
      console.error("Failed to fetch screening", e);
    }
  }, [jobId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openRankingSocket = useCallback(
    (runId: string) => {
      if (!runId || socketsRef.current.has(runId)) return;

      const append = (msg: string) => {
        setActivityLines((lines) => [...lines.slice(-30), msg]);
      };

      const wsUrl = `${apiWsBase()}/api/v1/ws/screening/${runId}`;
      const ws = new WebSocket(wsUrl);
      socketsRef.current.set(runId, ws);

      ws.onopen = () => {
        append("Connected - Analyzing all candidates...");
      };

      ws.onmessage = (ev) => {
        const raw = ev.data as string;
        if (isScreeningTerminalEvent(raw)) {
          append("Ranking complete!");
          setIsRanking(false);
          void refresh();
          ws.close();
          return;
        }
        const line = friendlyScreeningMessage(raw);
        if (line) append(line);
      };

      ws.onerror = () => {
        append("Connection issue during ranking.");
        setIsRanking(false);
        void refresh();
      };

      ws.onclose = () => {
        socketsRef.current.delete(runId);
      };
    },
    [refresh],
  );

  const handleRankAll = async () => {
    if (isRanking) return;
    setIsRanking(true);
    setActivityLines(["Initializing joint candidate analysis..."]);
    try {
      const res = await rankCandidates(jobId);
      if (res.screening_run_id) {
        openRankingSocket(res.screening_run_id);
      }
    } catch (e) {
      console.error(e);
      setIsRanking(false);
      setActivityLines(["Failed to start ranking. Make sure candidates are uploaded."]);
    }
  };

  const hasRanking = screening?.ranking && screening.ranking.trim().length > 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <Card className="border-[var(--accent)]/20 shadow-soft">
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div className="space-y-1">
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-yellow-500" />
                  AI Comparative Ranking
                </CardTitle>
                <CardDescription>
                  The AI analyzes all candidates concurrently to produce a relative force-ranking.
                </CardDescription>
              </div>
              <Button 
                onClick={handleRankAll} 
                disabled={isRanking}
                size="sm"
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90"
              >
                {isRanking ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Ranking...
                  </>
                ) : (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    {hasRanking ? "Regenerate Ranking" : "Generate Ranking"}
                  </>
                )}
              </Button>
            </CardHeader>
            <CardContent>
              {!hasRanking && !isRanking ? (
                <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed rounded-xl bg-muted/20 border-border/60">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted shadow-sm mb-4">
                    <ListOrdered className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-medium">No ranking generated yet</h3>
                  <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                    Click the button above to compare all candidates for this position.
                  </p>
                </div>
              ) : (
                <div className="relative">
                  {isRanking && (
                    <div className="absolute inset-0 z-10 flex items-center justify-center bg-card/60 backdrop-blur-[1px] rounded-lg">
                      <div className="flex flex-col items-center gap-3">
                        <Loader2 className="h-8 w-8 animate-spin text-[var(--accent)]" />
                        <p className="text-sm font-medium animate-pulse">AI is thinking...</p>
                      </div>
                    </div>
                  )}
                  <div className="space-y-4">
                    {screening?.ranking?.split("\n").map((line, idx) => {
                      if (line.includes("(No text returned from the chat model")) {
                        return (
                          <div key={idx} className="p-4 rounded-lg border border-destructive/20 bg-destructive/5 text-destructive text-sm">
                            <p className="font-semibold">AI Service Error</p>
                            <p className="mt-1 opacity-90">{line}</p>
                          </div>
                        );
                      }
                      const match = line.match(/^(\d+)\.\s*(.*?)(?::|—|-)\s*(.*)$/);
                      if (match) {
                        const [, rank, name, reason] = match;
                        return (
                          <div key={idx} className="flex items-start gap-4 p-4 rounded-xl border bg-card hover:border-[var(--accent)]/30 transition-all shadow-sm">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/10 text-[var(--accent)] font-bold text-lg border border-[var(--accent)]/20">
                              {rank}
                            </div>
                            <div className="space-y-1">
                              <h4 className="font-semibold text-foreground text-base">{name}</h4>
                              <p className="text-sm text-muted-foreground leading-relaxed">{reason}</p>
                            </div>
                          </div>
                        );
                      }
                      if (line.trim().length === 0) return null;
                      return (
                        <p key={idx} className="text-sm text-muted-foreground px-4 py-1 italic">
                          {line}
                        </p>
                      );
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">Ranking Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Last updated</span>
                <span className="font-medium">
                  {screening?.created_at ? new Date(screening.created_at).toLocaleString() : "Never"}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Status</span>
                <Badge variant={screening?.status === "complete" ? "accent" : "outline"}>
                  {screening?.status || "N/A"}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {(isRanking || activityLines.length > 0) && (
            <Card className="border-border/80 border-[var(--accent)]/25">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">AI Activity Log</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="max-h-48 space-y-2 overflow-y-auto text-xs text-muted-foreground">
                  {activityLines.map((line, i) => (
                    <li key={i} className="flex gap-2 border-b border-border/40 pb-1.5 last:border-0">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-[var(--accent)]" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
