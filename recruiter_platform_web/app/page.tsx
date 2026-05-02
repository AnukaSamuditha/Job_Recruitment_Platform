"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import JobCard from "@/components/jobs/JobCard";
import { useJobs } from "@/lib/hooks/useJobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  const { data: jobs = [], isLoading } = useJobs();

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 space-y-0">
          <div className="space-y-1">
            <CardDescription>Open roles</CardDescription>
            <CardTitle className="text-3xl font-semibold tracking-tight">Jobs</CardTitle>
            <p className="text-sm text-muted-foreground">Create postings, upload CVs, and review applicants.</p>
          </div>
          <Button asChild className="rounded-full">
            <Link href="/jobs/new">
              <Plus className="h-4 w-4" />
              Create job
            </Link>
          </Button>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading ? (
          <Card>
            <CardContent className="py-8 text-sm text-muted-foreground">Loading jobs…</CardContent>
          </Card>
        ) : (
          <>
            {jobs.map((j) => (
              <JobCard key={j.id} job={j} />
            ))}
            <Card className="border-dashed border-border/80 bg-muted/20 shadow-none">
              <CardContent className="flex min-h-[140px] items-center justify-center py-8">
                <Button variant="ghost" asChild className="text-[var(--accent)]">
                  <Link href="/jobs/new" aria-label="Create a new job">
                    <Plus className="h-4 w-4" />
                    New job
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
