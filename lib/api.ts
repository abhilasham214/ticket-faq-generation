export interface TicketPreview {
  id: number;
  external_id: string;
  subject: string;
}

export interface UploadResponse {
  ticket_count: number;
  preview: TicketPreview[];
}

export interface Faq {
  question: string;
  answer: string;
}

export interface Cluster {
  cluster_id: number;
  theme_title: string;
  ticket_count: number;
  ticket_ids: string[];
  top_terms: string[];
  faq: Faq;
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

export async function uploadTicketsCsv(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/tickets/upload", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}

export async function generateFaqs(): Promise<GenerateResponse> {
  const res = await fetch("/api/faqs/generate", { method: "POST" });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}

export async function fetchFaqs(): Promise<GenerateResponse> {
  const res = await fetch("/api/faqs", { method: "GET" });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return res.json();
}
