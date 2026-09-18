"use client";

import { useState } from "react";

import { type GenerateResponse } from "@/lib/api";
import { ClusterCard } from "@/components/cluster-card";
import { FaqGenerator } from "@/components/faq-generator";

export default function Home() {
  const [result, setResult] = useState<GenerateResponse | null>(null);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Base FAQ Auto Builder</h1>
        <p className="text-sm text-muted-foreground">
          Upload resolved support tickets to cluster them into recurring issue themes and draft a
          practical FAQ entry for each one.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">Upload resolved tickets (CSV)</h2>
        <FaqGenerator onGenerated={setResult} />
      </section>

      {result && result.clusters.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {result.clusters.length} themes across {result.total_tickets} tickets
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {result.clusters.map((cluster) => (
              <ClusterCard key={cluster.cluster_id} cluster={cluster} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
