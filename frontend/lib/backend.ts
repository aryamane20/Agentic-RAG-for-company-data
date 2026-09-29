// Server-side only: the FastAPI base URL and the session cookie contract.
// Never imported from a client component -- route handlers and
// middleware are the only callers.

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export const SESSION_COOKIE = "solstice_session";

// Matches backend/auth.py's JWT_EXPIRY_MINUTES so the cookie never
// outlives the token it holds.
export const SESSION_MAX_AGE_SECONDS = 30 * 60;

export type Role = "engineer" | "hr_staff" | "executive";

export interface MeResponse {
  name: string;
  email: string;
  role: Role;
}

export interface ChatResponse {
  answer: string;
  source_documents: string[];
  conversation_id: string;
  message_id: string;
  hit_cap: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface PersistedMessage {
  role: "user" | "assistant";
  content: string;
  source_documents: string[];
  created_at: string;
}

export const REFUSAL_TEXT =
  "I don't have information about that based on the documents available to me.";
