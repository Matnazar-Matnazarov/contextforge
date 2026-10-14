"use client";

import { Download, RefreshCw, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useOrg } from "@/components/org-context";
import { StatusBadge } from "@/components/status-badge";
import { Alert, Button, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { errorMessage, formatBytes } from "@/lib/api";
import { useDeleteDocument, useDocuments, useReindex, useUpload } from "@/lib/queries";
import { ALLOWED_EXTENSIONS, MAX_UPLOAD_MB, validateFile } from "@/lib/schemas";

export default function DocumentsPage() {
  const { org } = useOrg();
  const docs = useDocuments(org.id);
  const upload = useUpload(org.id);
  const reindex = useReindex(org.id);
  const remove = useDeleteDocument(org.id);
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<{ name: string; pct: number }[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  async function handleFiles(files: FileList | File[]) {
    setErrors([]);
    for (const file of Array.from(files)) {
      const problem = validateFile(file);
      if (problem) {
        setErrors((e) => [...e, `${file.name}: ${problem}`]);
        continue;
      }
      setProgress((p) => [...p, { name: file.name, pct: 0 }]);
      try {
        await upload.mutateAsync({
          file,
          onProgress: (pct) => setProgress((p) => p.map((x) => (x.name === file.name ? { ...x, pct } : x))),
        });
      } catch (e) {
        setErrors((errs) => [...errs, `${file.name}: ${errorMessage(e)}`]);
      } finally {
        setProgress((p) => p.filter((x) => x.name !== file.name));
      }
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <PageHeader title="Documents">
        <Button onClick={() => input.current?.click()}>
          <Upload size={16} aria-hidden /> Upload
        </Button>
      </PageHeader>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        aria-label="Upload documents"
        accept={ALLOWED_EXTENSIONS.join(",")}
        onChange={(e) => {
          if (e.target.files) void handleFiles(e.target.files);
          e.target.value = "";
        }}
      />

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void handleFiles(e.dataTransfer.files); }}
        className={`mb-6 rounded-xl border-2 border-dashed px-6 py-6 text-center text-sm ${dragging ? "border-accent bg-accentsoft" : "border-line text-muted"}`}
      >
        Drag &amp; drop PDF, TXT or Markdown files here (max {MAX_UPLOAD_MB} MB each).
      </div>

      {errors.length > 0 && (
        <div className="mb-4 space-y-2" aria-live="polite">
          {errors.map((e) => <Alert key={e}>{e}</Alert>)}
        </div>
      )}
      {progress.map((p) => (
        <div key={p.name} className="mb-3">
          <div className="mb-1 flex justify-between text-xs text-muted"><span>{p.name}</span><span>{p.pct}%</span></div>
          <div role="progressbar" aria-label={`Uploading ${p.name}`} aria-valuenow={p.pct} aria-valuemin={0} aria-valuemax={100} className="h-1.5 overflow-hidden rounded bg-surface2">
            <div className="h-full bg-accent transition-all" style={{ width: `${p.pct}%` }} />
          </div>
        </div>
      ))}
      {(reindex.isError || remove.isError) && <div className="mb-4"><Alert>{errorMessage(reindex.error ?? remove.error)}</Alert></div>}

      {docs.isLoading && <Spinner label="Loading documents…" />}
      {docs.isError && <Alert>{errorMessage(docs.error)}</Alert>}
      {docs.data?.results.length === 0 && (
        <EmptyState title="No documents yet">Upload a document to start asking questions about it.</EmptyState>
      )}
      {!!docs.data?.results.length && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <caption className="sr-only">Documents in {org.name}</caption>
            <thead className="bg-surface2 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5">Name</th>
                <th scope="col" className="px-4 py-2.5">Status</th>
                <th scope="col" className="hidden px-4 py-2.5 sm:table-cell">Size</th>
                <th scope="col" className="hidden px-4 py-2.5 md:table-cell">Uploaded by</th>
                <th scope="col" className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {docs.data.results.map((d) => (
                <tr key={d.id}>
                  <td className="max-w-[16rem] px-4 py-3">
                    <p className="truncate font-medium" title={d.original_filename}>{d.original_filename}</p>
                    {d.status === "indexed" && <p className="text-xs text-muted">{d.chunk_count} passages{d.page_count ? ` · ${d.page_count} pages` : ""}</p>}
                    {d.status === "failed" && <p className="text-xs text-danger" role="note">{d.error_message || "Indexing failed."}</p>}
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                  <td className="hidden px-4 py-3 text-muted sm:table-cell">{formatBytes(d.size_bytes)}</td>
                  <td className="hidden px-4 py-3 text-muted md:table-cell">{d.uploaded_by_email ?? "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <a
                        href={`/api/orgs/${org.id}/documents/${d.id}/download/`}
                        aria-label={`Download ${d.original_filename}`}
                        className="rounded-lg p-2 text-muted hover:bg-surface2 hover:text-fg"
                      >
                        <Download size={16} aria-hidden />
                      </a>
                      {d.can_manage && (d.status === "failed" || d.status === "indexed" || d.status === "pending") && (
                        <Button variant="ghost" aria-label={`${d.status === "failed" ? "Retry" : "Re-index"} ${d.original_filename}`} onClick={() => reindex.mutate(d.id)} className="!p-2">
                          <RefreshCw size={16} aria-hidden />
                          {d.status === "failed" && <span className="text-xs">Retry</span>}
                        </Button>
                      )}
                      {d.can_manage && (
                        <Button
                          variant="ghost"
                          aria-label={`Delete ${d.original_filename}`}
                          className="!p-2 hover:!text-danger"
                          onClick={() => { if (confirm(`Delete "${d.original_filename}"? This also removes its indexed passages.`)) remove.mutate(d.id); }}
                        >
                          <Trash2 size={16} aria-hidden />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
