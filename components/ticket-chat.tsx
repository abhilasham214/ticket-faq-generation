"use client";

import { useState } from "react";

import { ApiError, askAboutTicket, type TicketSummary } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TicketChatProps {
  ticket: TicketSummary;
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

// Grounded strictly in this one ticket's own subject/description/resolution
// (see api/_lib/ticket_qa.py) - no cross-ticket context, and no client-side
// history is sent back to the API, so each question is answered fresh from
// just the ticket fields every time.
export function TicketChat({ ticket }: TicketChatProps) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk() {
    const trimmed = question.trim();
    if (!trimmed || asking) return;

    setAsking(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setQuestion("");

    try {
      const result = await askAboutTicket(ticket, trimmed);
      setMessages((prev) => [...prev, { role: "assistant", text: result.answer }]);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not get an answer. Please try again."
      );
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="mt-2 flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-2">
      {messages.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {messages.map((message, i) => (
            <li key={i} className="text-xs">
              <span className="font-semibold text-foreground">
                {message.role === "user" ? "You: " : "Answer: "}
              </span>
              <span className={message.role === "user" ? "text-foreground" : "text-muted-foreground"}>
                {message.text}
              </span>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t get an answer</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-1.5">
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleAsk();
          }}
          placeholder="Ask about this ticket..."
          disabled={asking}
          className="h-7 text-xs"
        />
        <Button size="xs" onClick={handleAsk} disabled={asking || !question.trim()}>
          {asking ? "Asking..." : "Ask"}
        </Button>
      </div>
    </div>
  );
}
