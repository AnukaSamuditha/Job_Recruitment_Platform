"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import RateCandidates from "@/components/jobs/RateCandidates";
import JobRanking from "@/components/jobs/JobRanking";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useJob } from "@/lib/hooks/useJobs";

export default function JobWorkspace() {
  const params = useParams();
  const id = Array.isArray(params?.id) ? params.id[0] : params?.id ?? "unknown";
  const [tab, setTab] = useState<"details" | "rate" | "rank">("details");
  const { data: job, isLoading } = useJob(id);

  const title = job?.title ?? (isLoading ? "Loading…" : "Job");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Job workspace</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{title}</h1>
          {job?.company && <p className="mt-1 text-sm text-muted-foreground">{job.company}</p>}
        </div>
        <div className="flex rounded-lg border border-border/70 bg-muted/30 p-1 shadow-soft">
          <Button
            type="button"
            variant={tab === "details" ? "default" : "ghost"}
            size="sm"
            className={tab === "details" ? "rounded-md shadow-none" : "rounded-md"}
            onClick={() => setTab("details")}
          >
            Overview
          </Button>
          <Button
            type="button"
            variant={tab === "rate" ? "default" : "ghost"}
            size="sm"
            className={tab === "rate" ? "rounded-md shadow-none" : "rounded-md"}
            onClick={() => setTab("rate")}
          >
            Candidates
          </Button>
          <Button
            type="button"
            variant={tab === "rank" ? "default" : "ghost"}
            size="sm"
            className={tab === "rank" ? "rounded-md shadow-none" : "rounded-md"}
            onClick={() => setTab("rank")}
          >
            AI Ranking
          </Button>
        </div>
      </div>

      {tab === "details" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Role summary</CardTitle>
            <CardDescription>Posting details and expectations.</CardDescription>
          </CardHeader>
          <div className="px-6 pb-6">
            {job?.description ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{job.description}</p>
            ) : (
              <p className="text-sm text-muted-foreground">
                {isLoading ? "Loading job details…" : "No description was provided for this job."}
              </p>
            )}
          </div>
        </Card>
      )}

      {tab === "rate" && <RateCandidates jobId={id} />}
      {tab === "rank" && <JobRanking jobId={id} />}
    </div>
  );
}
