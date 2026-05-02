"use client";

import React, { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Gem } from "lucide-react";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <header className="w-full border-b border-border/80 bg-card shadow-soft">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent)]/12">
            <Gem className="h-5 w-5 text-[var(--accent)]" aria-hidden />
          </div>
          <div>
            <p className="text-lg font-semibold tracking-tight">Recruiter portal</p>
            <p className="text-xs text-muted-foreground">Hiring workspace</p>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
      </main>
    </QueryClientProvider>
  );
}
