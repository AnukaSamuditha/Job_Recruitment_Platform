"use client";

import React from "react";
import Link from "next/link";
import { Briefcase, MapPin, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

type Job = {
  id: string;
  title: string;
  company: string;
  location?: string;
  posted?: string;
};

export default function JobCard({ job }: { job: Job }) {
  return (
    <Link href={`/jobs/${job.id}`} className="block h-full">
      <Card className="h-full transition-[border-color,box-shadow] hover:border-[var(--accent)]/35">
        <CardContent className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">{job.title}</h2>
              <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                <Briefcase className="h-4 w-4 shrink-0" aria-hidden />
                {job.company}
              </p>
              {job.location && (
                <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {job.location}
                </p>
              )}
            </div>
            <div className="text-right">
              {job.posted && (
                <p className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {job.posted}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
