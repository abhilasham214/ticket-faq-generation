"use client";

import { useEffect, useState } from "react";

import { ApiError, generateFaqs, type GenerateResponse } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface FaqGeneratorProps {
  onGenerated: (result: GenerateResponse) => void;
}

// The backend does clustering + FAQ drafting in one blocking request with no
// progress events, so these are a rough staged approximation - not tied to
// real backend progress - purely to reassure the user during the wait.
const LOADING_STAGES = [
  "Analyzing tickets...",
  "Grouping recurring issues...",
  "Drafting FAQs...",
];

export function FaqGenerator({ onGenerated }: FaqGeneratorProps) {
  const [file, setFile] = useState<File | null>(null);
  const [generating, setGenerating] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!generating) return;
    const interval = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, LOADING_STAGES.length - 1));
    }, 1400);
    return () => clearInterval(interval);
  }, [generating]);

  async function handleGenerate() {
    if (!file) return;
    setStageIndex(0);
    setGenerating(true);
    setError(null);
    try {
      const result = await generateFaqs(file);
      onGenerated(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate FAQs. Please try again.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={generating}
          className="sm:max-w-xs"
        />
        <Button onClick={handleGenerate} disabled={!file || generating}>
          {generating ? LOADING_STAGES[stageIndex] : "Generate FAQs"}
        </Button>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Generation failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
