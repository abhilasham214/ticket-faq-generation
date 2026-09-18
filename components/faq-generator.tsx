"use client";

import { useState } from "react";

import { ApiError, generateFaqs, type GenerateResponse } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface FaqGeneratorProps {
  onGenerated: (result: GenerateResponse) => void;
}

export function FaqGenerator({ onGenerated }: FaqGeneratorProps) {
  const [file, setFile] = useState<File | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    if (!file) return;
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
          className="sm:max-w-xs"
        />
        <Button onClick={handleGenerate} disabled={!file || generating}>
          {generating ? "Generating..." : "Generate FAQs"}
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
