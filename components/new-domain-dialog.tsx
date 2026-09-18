"use client";

import { useState } from "react";

import { addCustomCategory, ApiError, type Cluster } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface NewDomainDialogProps {
  clusters: Cluster[];
}

// AI-named clusters are ones that didn't match any curated domain category
// (see api/_lib/cluster_naming.py's has_curated_match) and got a one-off
// Gemini-suggested name instead. This surfaces each one, once, so a human
// can decide whether it's a genuinely new recurring theme worth making
// permanent or just a one-off for this batch.
export function NewDomainDialog({ clusters }: NewDomainDialogProps) {
  // Reset which clusters have been reviewed whenever a fresh generate result
  // comes in, without an effect - adjusting state during render when a prop
  // changes identity is the recommended alternative to a setState-in-effect
  // (see https://react.dev/learn/you-might-not-need-an-effect).
  const [prevClusters, setPrevClusters] = useState(clusters);
  const [reviewedIds, setReviewedIds] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (clusters !== prevClusters) {
    setPrevClusters(clusters);
    setReviewedIds(new Set());
    setError(null);
  }

  const queue = clusters.filter((c) => c.ai_named && !reviewedIds.has(c.cluster_id));
  const current = queue[0];

  function dismiss(clusterId: number) {
    setError(null);
    setReviewedIds((prev) => new Set(prev).add(clusterId));
  }

  async function handleAddAsDomain() {
    if (!current) return;
    setSaving(true);
    setError(null);
    try {
      await addCustomCategory(current.theme, current.discovered_keywords);
      dismiss(current.cluster_id);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not save the new domain. Please try again."
      );
    } finally {
      setSaving(false);
    }
  }

  if (!current) return null;

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) dismiss(current.cluster_id);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New domain detected</DialogTitle>
          <DialogDescription>
            &ldquo;{current.theme}&rdquo; didn&apos;t match any existing category, so Gemini
            named it from its own keywords. Add it as a permanent domain so future uploads
            recognize this theme automatically, or just use it for this batch.
          </DialogDescription>
        </DialogHeader>

        {current.discovered_keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {current.discovered_keywords.map((kw) => (
              <Badge key={kw} variant="outline">
                {kw}
              </Badge>
            ))}
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Couldn&apos;t save</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => dismiss(current.cluster_id)} disabled={saving}>
            Just categorize this batch
          </Button>
          <Button onClick={handleAddAsDomain} disabled={saving}>
            {saving ? "Adding..." : "Add as new domain"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
