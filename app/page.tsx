"use client";

import { useState } from "react";

import { type GenerateResponse } from "@/lib/api";
import { ClusterCard } from "@/components/cluster-card";
import { FaqGenerator } from "@/components/faq-generator";
import { NewDomainDialog } from "@/components/new-domain-dialog";

export default function Home() {
  const [result, setResult] = useState<GenerateResponse | null>(null);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Base FAQ Auto Builder</h1>
        <p className="text-sm text-muted-foreground">
          Turn resolved support tickets into reusable team knowledge.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">Upload resolved tickets (CSV)</h2>
        <FaqGenerator onGenerated={setResult} />
      </section>

      {result && <NewDomainDialog clusters={result.clusters} />}

      {result && result.clusters.length > 0 ? (
        <section className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold">{result.total_tickets} Tickets</span>
            <span className="text-muted-foreground">|</span>
            <span className="font-semibold">{result.clusters.length} Themes</span>
            <span className="text-muted-foreground">|</span>
            <span className="font-semibold">{result.clusters.length} FAQs</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {result.clusters.map((cluster) => (
              <ClusterCard key={cluster.cluster_id} cluster={cluster} />
            ))}
          </div>
        </section>
      ) : (
        <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Upload a CSV of resolved support tickets and click &ldquo;Generate FAQs&rdquo; to
          detect recurring themes and draft a knowledge-base entry for each one.
        </p>
      )}
    </div>
  );
}
