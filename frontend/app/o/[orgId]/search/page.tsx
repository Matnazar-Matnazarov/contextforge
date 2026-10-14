"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { useOrg } from "@/components/org-context";
import { Alert, Button, Card, EmptyState, Field, PageHeader, Spinner } from "@/components/ui";
import { useSearch } from "@/lib/queries";

export default function SearchPage() {
  const { org } = useOrg();
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const search = useSearch(org.id, query);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <PageHeader title="Search" />
      <form
        role="search"
        className="mb-6 flex items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(input.trim());
        }}
      >
        <div className="flex-1">
          <Field label="Search passages" placeholder="e.g. TLS 1.3 handshake" value={input} onChange={(e) => setInput(e.target.value)} />
        </div>
        <Button type="submit" disabled={input.trim().length < 2}>
          <Search size={16} aria-hidden /> Search
        </Button>
      </form>
      {search.isFetching && <Spinner label="Searching…" />}
      {search.error && <Alert>Search failed. Please try again.</Alert>}
      {search.data && search.data.results.length === 0 && (
        <EmptyState title="No matching passages">Try different words, or check that documents are indexed.</EmptyState>
      )}
      <ul className="space-y-3">
        {search.data?.results.map((r, i) => (
          <li key={`${r.document_id}-${i}`}>
            <Card className="p-4">
              <p className="text-sm font-semibold">
                {r.document_name}
                {r.page ? <span className="ml-2 font-normal text-muted">p. {r.page}</span> : null}
                {r.section ? <span className="ml-2 font-normal text-muted">{r.section}</span> : null}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted">{r.excerpt}</p>
              <a className="mt-2 inline-block text-xs text-accent hover:underline" href={`/api/orgs/${org.id}/documents/${r.document_id}/download/`}>
                Download original
              </a>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
