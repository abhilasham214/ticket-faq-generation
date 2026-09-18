"use client";

import { useEffect, useState } from "react";

import {
  ApiError,
  fetchFaqs,
  generateFaqs,
  type GenerateResponse,
  type UploadResponse,
} from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ClusterCard } from "@/components/cluster-card";
import { TicketUpload } from "@/components/ticket-upload";

export default function Home() {
  const [uploaded, setUploaded] = useState<UploadResponse | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFaqs()
      .then((data) => {
        if (data.clusters.length > 0) setResult(data);
      })
      .catch(() => {
        // No prior FAQs yet - nothing to show, and nothing to alarm the user with.
      });
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const data = await generateFaqs();
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate FAQs. Please try again.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Base FAQ Auto Builder</h1>
        <p className="text-sm text-muted-foreground">
          Upload resolved support tickets, cluster them into recurring issue themes, and draft a
          practical FAQ entry for each one.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">1. Upload resolved tickets (CSV)</h2>
        <TicketUpload onUploaded={setUploaded} />
        {uploaded && (
          <p className="text-sm text-muted-foreground">
            Loaded {uploaded.ticket_count} tickets.
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">2. Generate FAQ themes</h2>
        <div>
          <Button onClick={handleGenerate} disabled={!uploaded || generating}>
            {generating ? "Generating..." : "Generate FAQs"}
          </Button>
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Generation failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
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
