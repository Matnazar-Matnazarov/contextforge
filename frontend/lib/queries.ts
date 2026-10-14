"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, uploadFile } from "./api";
import type {
  ChatMessage,
  Conversation,
  DocumentItem,
  Member,
  Organization,
  Paginated,
  Role,
  User,
} from "./types";

export interface SearchResult {
  document_id: string;
  document_name: string;
  page: number | null;
  section: string | null;
  excerpt: string;
}

export const keys = {
  me: ["me"] as const,
  orgs: ["orgs"] as const,
  docs: (org: string) => ["orgs", org, "documents"] as const,
  members: (org: string) => ["orgs", org, "members"] as const,
  convs: (org: string) => ["orgs", org, "conversations"] as const,
  messages: (org: string, conv: string) => ["orgs", org, "conversations", conv, "messages"] as const,
};

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      try {
        return await api<User>("/auth/me/");
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return null;
        throw e;
      }
    },
  });
}

export const useOrgs = () => useQuery({ queryKey: keys.orgs, queryFn: () => api<Organization[]>("/orgs/") });

export function useCreateOrg() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api<Organization>("/orgs/", { method: "POST", json: { name } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.orgs }),
  });
}

export function useDocuments(orgId: string) {
  return useQuery({
    queryKey: keys.docs(orgId),
    queryFn: () => api<Paginated<DocumentItem>>(`/orgs/${orgId}/documents/?page_size=100`),
    // Poll while anything is still being indexed; stop when everything is settled.
    refetchInterval: (q) =>
      q.state.data?.results.some((d) => d.status === "pending" || d.status === "processing") ? 2500 : false,
  });
}

export function useUpload(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress: (p: number) => void }) =>
      uploadFile<DocumentItem>(`/orgs/${orgId}/documents/`, file, onProgress),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.docs(orgId) }),
  });
}

export function useReindex(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/orgs/${orgId}/documents/${id}/reindex/`, { method: "POST" }),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.docs(orgId) }),
  });
}

export function useDeleteDocument(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/orgs/${orgId}/documents/${id}/`, { method: "DELETE" }),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.docs(orgId) }),
  });
}

export const useMembers = (orgId: string) =>
  useQuery({ queryKey: keys.members(orgId), queryFn: () => api<Member[]>(`/orgs/${orgId}/members/`) });

export function useMemberMutations(orgId: string) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: keys.members(orgId) });
  return {
    add: useMutation({
      mutationFn: (v: { email: string; role: Role }) => api(`/orgs/${orgId}/members/`, { method: "POST", json: v }),
      onSuccess: refresh,
    }),
    changeRole: useMutation({
      mutationFn: (v: { id: string; role: Role }) =>
        api(`/orgs/${orgId}/members/${v.id}/`, { method: "PATCH", json: { role: v.role } }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api(`/orgs/${orgId}/members/${id}/`, { method: "DELETE" }),
      onSuccess: refresh,
    }),
  };
}

export const useConversations = (orgId: string) =>
  useQuery({
    queryKey: keys.convs(orgId),
    queryFn: () => api<Paginated<Conversation>>(`/orgs/${orgId}/conversations/?page_size=50`),
  });

export function useCreateConversation(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<Conversation>(`/orgs/${orgId}/conversations/`, { method: "POST", json: {} }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.convs(orgId) }),
  });
}

export function useDeleteConversation(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/orgs/${orgId}/conversations/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.convs(orgId) }),
  });
}

export const useMessages = (orgId: string, convId: string | null) =>
  useQuery({
    queryKey: keys.messages(orgId, convId ?? "none"),
    enabled: !!convId,
    queryFn: () => api<ChatMessage[]>(`/orgs/${orgId}/conversations/${convId}/messages/`),
  });

export function useAsk(orgId: string, convId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (question: string) =>
      api<{ user_message: ChatMessage; assistant_message: ChatMessage }>(
        `/orgs/${orgId}/conversations/${convId}/messages/`,
        { method: "POST", json: { question } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.messages(orgId, convId) });
      qc.invalidateQueries({ queryKey: keys.convs(orgId) });
    },
  });
}

export function useSearch(orgId: string, query: string) {
  return useQuery({
    queryKey: ["orgs", orgId, "search", query] as const,
    enabled: query.length >= 2,
    queryFn: () => api<{ query: string; results: SearchResult[] }>(`/orgs/${orgId}/search/?q=${encodeURIComponent(query)}`),
  });
}
