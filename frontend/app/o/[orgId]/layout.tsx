"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { MessageSquare, FileText, Users, ArrowLeftRight, Search } from "lucide-react";
import { OrgContext } from "@/components/org-context";
import { Alert, Spinner } from "@/components/ui";
import { UserMenu } from "@/components/user-menu";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { useOrgs } from "@/lib/queries";

const nav = [
  { href: "chat", label: "Chat", icon: MessageSquare },
  { href: "search", label: "Search", icon: Search },
  { href: "documents", label: "Documents", icon: FileText },
  { href: "members", label: "Members", icon: Users },
];

export default function OrgLayout({ children }: { children: React.ReactNode }) {
  const { orgId } = useParams<{ orgId: string }>();
  const pathname = usePathname();
  const me = useRequireAuth();
  const orgs = useOrgs();
  const org = orgs.data?.find((o) => o.id === orgId);

  if (me.isLoading || orgs.isLoading || !me.data) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner label="Loading workspace…" /></div>;
  }
  if (!org || !org.role) {
    return (
      <main id="main" className="mx-auto max-w-lg px-4 py-16">
        <Alert>Organization not found, or you are not a member.</Alert>
        <Link href="/orgs" className="mt-4 inline-block text-sm text-accent underline">Back to organizations</Link>
      </main>
    );
  }

  return (
    <OrgContext.Provider value={{ org, role: org.role }}>
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="border-b border-line bg-surface md:w-60 md:shrink-0 md:border-b-0 md:border-r">
          <div className="flex items-center justify-between gap-2 px-4 py-4 md:block">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-accent">Knowledge Hub</p>
              <p className="mt-1 truncate font-semibold" title={org.name}>{org.name}</p>
              <p className="text-xs capitalize text-muted">{org.role}</p>
            </div>
            <Link href="/orgs" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg md:mt-3">
              <ArrowLeftRight size={14} aria-hidden /> Switch
            </Link>
          </div>
          <nav aria-label="Workspace" className="flex gap-1 px-2 pb-2 md:flex-col md:pb-4">
            {nav.map(({ href, label, icon: Icon }) => {
              const to = `/o/${orgId}/${href}`;
              const active = pathname.startsWith(to);
              return (
                <Link
                  key={href}
                  href={to}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${active ? "bg-accentsoft text-accent" : "text-muted hover:bg-surface2 hover:text-fg"}`}
                >
                  <Icon size={16} aria-hidden /> {label}
                </Link>
              );
            })}
          </nav>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex justify-end border-b border-line bg-surface px-4 py-2.5"><UserMenu /></header>
          <main id="main" className="min-h-0 flex-1">{children}</main>
        </div>
      </div>
    </OrgContext.Provider>
  );
}
