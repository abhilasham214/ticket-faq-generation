export interface Faq {
  question: string;
  answer: string;
  resolution_steps: string[];
  escalation: string;
}

export interface TicketSummary {
  ticket_id: string;
  title: string;
  description: string;
  resolution: string;
}

export interface Cluster {
  cluster_id: number;
  theme: string;
  ai_named: boolean;
  discovered_keywords: string[];
  ticket_count: number;
  keywords: string[];
  ticket_ids: string[];
  tickets: TicketSummary[];
  faq: Faq;
}

export interface Category {
  id: string;
  label: string;
  keywords: string[];
}

export interface GenerateResponse {
  clusters: Cluster[];
  total_tickets: number;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // response body wasn't JSON - fall through to the generic message
  }
  return `Request failed with status ${res.status}`;
}

export async function generateFaqs(file: File): Promise<GenerateResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/faqs/generate", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}

export async function getLatestFaqs(): Promise<GenerateResponse> {
  const res = await fetch("/api/faqs/latest");

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}

export async function generateFaqsFromSample(): Promise<GenerateResponse> {
  const res = await fetch("/api/faqs/generate/sample", { method: "POST" });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}

export async function askAboutTicket(ticket: TicketSummary, question: string): Promise<{ answer: string }> {
  const res = await fetch("/api/tickets/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: ticket.title,
      description: ticket.description,
      resolution: ticket.resolution,
      question,
    }),
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}

export async function addCustomCategory(label: string, keywords: string[]): Promise<Category> {
  const res = await fetch("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, keywords }),
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}
