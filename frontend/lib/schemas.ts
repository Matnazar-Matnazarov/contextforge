import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export const registerSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  display_name: z.string().max(150).optional(),
  password: z.string().min(10, "Use at least 10 characters"),
});

export const orgSchema = z.object({ name: z.string().trim().min(1, "Name is required").max(120) });

export const addMemberSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  role: z.enum(["member", "admin", "owner"]),
});

export const questionSchema = z.object({ question: z.string().trim().min(1, "Type a question").max(2000) });

export const ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md", ".markdown"];
export const MAX_UPLOAD_MB = 10;

export function validateFile(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) return "Unsupported file type. Use PDF, TXT or Markdown.";
  if (file.size === 0) return "File is empty.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `File exceeds the ${MAX_UPLOAD_MB} MB limit.`;
  return null;
}
