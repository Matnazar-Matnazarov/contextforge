"use client";

import { MessageSquarePlus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useOrg } from "@/components/org-context";
import { Spinner } from "@/components/ui";
import { useConversations, useDeleteConversation } from "@/lib/queries";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const { org } = useOrg();
  const params = useParams<{ conversationId?: string }>();
  const router = useRouter();
  const convs = useConversations(org.id);
  const remove = useDeleteConversation(org.id);

  return (
    <div className="flex h-[calc(100vh-3.25rem)] min-h-0 flex-col md:flex-row">
      <nav aria-label="Conversation history" className="max-h-40 shrink-0 overflow-y-auto border-b border-line bg-surface p-2 md:max-h-none md:w-64 md:border-b-0 md:border-r">
        <Link href={`/o/${org.id}/chat`} className="mb-2 flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm font-medium hover:border-accent">
          <MessageSquarePlus size={16} aria-hidden /> New chat
        </Link>
        {convs.isLoading && <Spinner label="Loading…" />}
        {convs.data?.results.length === 0 && <p className="px-2 py-3 text-xs text-muted">No conversations yet.</p>}
        <ul className="space-y-0.5">
          {convs.data?.results.map((c) => {
            const active = params.conversationId === c.id;
            return (
              <li key={c.id} className="group flex items-center">
                <Link
                  href={`/o/${org.id}/chat/${c.id}`}
                  aria-current={active ? "page" : undefined}
                  className={`min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-sm ${active ? "bg-accentsoft font-medium text-accent" : "text-muted hover:bg-surface2 hover:text-fg"}`}
                >
                  {c.title || "Untitled"}
                </Link>
                <button
                  type="button"
                  aria-label={`Delete conversation ${c.title || "Untitled"}`}
                  className="rounded p-1.5 text-muted opacity-0 hover:text-danger focus:opacity-100 group-hover:opacity-100"
                  onClick={async () => {
                    if (!confirm("Delete this conversation?")) return;
                    await remove.mutateAsync(c.id);
                    if (active) router.replace(`/o/${org.id}/chat`);
                  }}
                >
                  <Trash2 size={14} aria-hidden />
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="min-h-0 min-w-0 flex-1">{children}</div>
    </div>
  );
}
