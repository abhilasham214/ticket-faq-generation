"use client";

import { useState } from "react";

import type { Cluster } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { TicketChat } from "@/components/ticket-chat";

interface ClusterCardProps {
  cluster: Cluster;
}

export function ClusterCard({ cluster }: ClusterCardProps) {
  const [openChatId, setOpenChatId] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <CardTitle>{cluster.theme}</CardTitle>
            {cluster.ai_named && (
              <Badge variant="outline" className="shrink-0 text-xs" title="No curated category matched; Gemini named this new theme from its keywords.">
                AI-named
              </Badge>
            )}
            {cluster.is_new_domain && !cluster.ai_named && (
              <Badge
                variant="destructive"
                className="shrink-0 text-xs"
                title="This theme doesn't match any curated category, and Gemini wasn't available to name it - this is a generic fallback name, not a reviewed category."
              >
                Gemini unavailable
              </Badge>
            )}
          </div>
          <Badge variant="secondary" className="shrink-0 text-sm font-semibold">
            {cluster.ticket_count} tickets
          </Badge>
        </div>
        {cluster.keywords.length > 0 && (
          <CardDescription>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {cluster.keywords.slice(0, 6).map((kw) => (
                <Badge key={kw} variant="outline">
                  {kw}
                </Badge>
              ))}
            </div>
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-1.5">
            <p className="text-sm font-medium">{cluster.faq.question}</p>
            {!cluster.faq.gemini_generated && (
              <Badge
                variant="destructive"
                className="shrink-0 text-xs"
                title="Gemini wasn't available when this was generated, so this FAQ is a template built directly from the ticket resolutions below, not a Gemini-drafted summary."
              >
                Templated
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{cluster.faq.answer}</p>
        </div>

        {cluster.faq.resolution_steps.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Resolution steps
            </p>
            <ol className="mt-1.5 flex flex-col gap-1 text-sm">
              {cluster.faq.resolution_steps.map((step, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-muted-foreground">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {cluster.faq.escalation && (
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Escalation
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{cluster.faq.escalation}</p>
          </div>
        )}

        <Collapsible>
          <CollapsibleTrigger className="text-left text-xs font-medium text-muted-foreground underline underline-offset-2 hover:text-foreground">
            Show source tickets ({cluster.tickets.length})
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="mt-2 flex flex-col gap-2">
              {cluster.tickets.map((t) => {
                const isOpen = openChatId === t.ticket_id;
                return (
                  <li key={t.ticket_id} className="rounded-md border border-border p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{t.ticket_id}</Badge>
                        <span className="font-medium">{t.title}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => setOpenChatId(isOpen ? null : t.ticket_id)}
                      >
                        {isOpen ? "Close" : "Discuss"}
                      </Button>
                    </div>
                    <p className="mt-1 line-clamp-2 text-muted-foreground">{t.resolution}</p>
                    {isOpen && <TicketChat ticket={t} />}
                  </li>
                );
              })}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}
