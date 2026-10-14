export type Role = "owner" | "admin" | "member";
export type DocumentStatus = "pending" | "processing" | "indexed" | "failed";

export interface User {
  id: string;
  email: string;
  display_name: string;
}

export interface Organization {
  id: string;
  name: string;
  role: Role | null;
  created_at: string;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: Role;
  status: "active" | "suspended";
  created_at: string;
}

export interface DocumentItem {
  id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string;
  page_count: number | null;
  chunk_count: number;
  uploaded_by_email: string | null;
  can_manage: boolean;
  created_at: string;
  indexed_at: string | null;
}

export interface Citation {
  id: string;
  document_id: string | null;
  document_title: string;
  chunk_id: string;
  source_label: string;
  page_number: number | null;
  section: string;
  excerpt: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  insufficient_context: boolean;
  citations: Citation[];
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
