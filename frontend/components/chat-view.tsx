"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { api, errorMessage } from "@/lib/api";
import { keys, useMessages } from "@/lib/queries";
import { questionSchema } from "@/lib/schemas";
import type { ChatMessage, Citation, Conversation } from "@/lib/types";
import { useOrg } from "./org-context";
import { Alert, Button, EmptyState, Spinner } from "./ui";

export function ChatView({ conversationId }: { conversationId: string | null }) {
  const { org } = useOrg();
  const router = useRouter();
  const qc = useQueryClient();
  const messages = useMessages(org.id, conversationId);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Citation | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const { register, handleSubmit, reset, formState: { errors } } = useForm<z.infer<typeof questionSchema>>({
    resolver: zodResolver(questionSchema),
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages.data, pending]);

  async function onSubmit({ question }: z.infer<typeof questionSchema>) {
    setError(null);
    setPending(question);
    reset();
    try {
      let id = conversationId;
      if (!id) {
        const conv = await api<Conversation>(`/orgs/${org.id}/conversations/`, { method: "POST", json: {} });
        id = conv.id;
      }
      await api(`/orgs/${org.id}/conversations/${id}/messages/`, { method: "POST", json: { question } });
      await Promise.all([
        qc.invalidateQueries({ queryKey: keys.messages(org.id, id) }),
        qc.invalidateQueries({ queryKey: keys.convs(org.id) }),
      ]);
      if (!conversationId) router.replace(`/o/${org.id}/chat/${id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(null);
    }
  }

  const list = messages.data ?? [];

  return (
    <div className="flex h-full min-h-0">
      <section className="flex min-w-0 flex-1 flex-col" aria-label="Conversation">
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-6 md:px-8" aria-live="polite">
          {messages.isLoading && conversationId && <Spinner label="Loading messages…" />}
          {messages.isError && <Alert>{errorMessage(messages.error)}</Alert>}
          {!conversationId && !pending && (
            <EmptyState title="Ask your documents anything">
              Answers are generated only from passages found in your organization&apos;s indexed documents, with sources.
            </EmptyState>
          )}
          {list.map((m) => (
            <MessageBubble key={m.id} message={m} onCite={setSelected} selectedId={selected?.id} />
          ))}
          {pending && (
            <>
              <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm text-accentfg">{pending}</div>
              <div className="flex items-center gap-2 text-sm text-muted"><Spinner label="Searching documents and writing an answer…" /></div>
            </>
          )}
          {error && <Alert>{error}</Alert>}
          <div ref={bottom} />
        </div>
        <form onSubmit={handleSubmit(onSubmit)} className="border-t border-line bg-surface p-3 md:p-4" noValidate>
          <div className="mx-auto flex max-w-3xl items-start gap-2">
            <div className="flex-1">
              <label htmlFor="question" className="sr-only">Your question</label>
              <textarea
                id="question"
                rows={2}
                placeholder="Ask a question about your documents…"
                aria-invalid={!!errors.question}
                className="w-full resize-none rounded-xl border border-line bg-bg px-3 py-2 text-sm"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
                {...register("question")}
              />
              {errors.question && <p role="alert" className="mt-1 text-xs text-danger">{errors.question.message}</p>}
            </div>
            <Button type="submit" loading={!!pending} aria-label="Send question" className="h-10">
              <Send size={16} aria-hidden />
            </Button>
          </div>
        </form>
      </section>

      {selected && (
        <aside aria-label="Source" className="hidden w-80 shrink-0 overflow-y-auto border-l border-line bg-surface p-4 lg:block">
          <SourcePanel citation={selected} orgId={org.id} onClose={() => setSelected(null)} />
        </aside>
      )}
      {selected && (
        <div className="fixed inset-x-0 bottom-0 z-20 max-h-[60vh] overflow-y-auto rounded-t-2xl border-t border-line bg-surface p-4 shadow-xl lg:hidden">
          <SourcePanel citation={selected} orgId={org.id} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message, onCite, selectedId }: { message: ChatMessage; onCite: (c: Citation) => void; selectedId?: string }) {
  if (message.role === "user") {
    return <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm text-accentfg">{message.content}</div>;
  }
  return (
    <div className="max-w-[90%] space-y-3">
      <div className={`whitespace-pre-wrap rounded-2xl rounded-bl-sm border px-4 py-3 text-sm leading-relaxed ${message.insufficient_context ? "border-warn/40 bg-warnsoft text-warn" : "border-line bg-surface"}`}>
        {message.insufficient_context && <p className="mb-1 text-xs font-semibold uppercase tracking-wide">Not enough information</p>}
        {message.content}
      </div>
      {message.citations.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-muted">Sources</p>
          <ul className="flex flex-wrap gap-2">
            {message.citations.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onCite(c)}
                  aria-pressed={selectedId === c.id}
                  className={`flex max-w-xs items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-left text-xs transition ${selectedId === c.id ? "border-accent bg-accentsoft" : "border-line bg-surface hover:border-accent"}`}
                >
                  <FileText size={13} aria-hidden className="shrink-0" />
                  <span className="font-semibold">{c.source_label}</span>
                  <span className="truncate">{c.document_title}</span>
                  {c.page_number != null && <span className="shrink-0 text-muted">p.{c.page_number}</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SourcePanel({ citation: c, orgId, onClose }: { citation: Citation; orgId: string; onClose: () => void }) {
  return (
    <div>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-accent">Source {c.source_label}</p>
          <h2 className="break-words font-semibold">{c.document_title}</h2>
          <p className="text-xs text-muted">
            {[c.page_number != null ? `Page ${c.page_number}` : null, c.section || null].filter(Boolean).join(" · ") || "Passage"}
          </p>
        </div>
        <Button variant="ghost" onClick={onClose} aria-label="Close source" className="!p-1.5"><X size={16} aria-hidden /></Button>
      </div>
      <blockquote className="whitespace-pre-wrap rounded-lg border-l-4 border-accent bg-surface2 p-3 text-sm leading-relaxed">{c.excerpt}</blockquote>
      {c.document_id ? (
        <a href={`/api/orgs/${orgId}/documents/${c.document_id}/download/`} className="mt-3 inline-flex items-center gap-1.5 text-sm text-accent underline">
          <Download size={14} aria-hidden /> Download original
        </a>
      ) : (
        <p className="mt-3 text-xs text-muted">The original document has since been deleted.</p>
      )}
    </div>
  );
}
