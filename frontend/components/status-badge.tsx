import type { DocumentStatus } from "@/lib/types";

const styles: Record<DocumentStatus, { cls: string; label: string }> = {
  pending: { cls: "bg-surface2 text-muted", label: "Pending" },
  processing: { cls: "bg-warnsoft text-warn", label: "Processing" },
  indexed: { cls: "bg-oksoft text-ok", label: "Indexed" },
  failed: { cls: "bg-dangersoft text-danger", label: "Failed" },
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const s = styles[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>
      <span
        aria-hidden
        className={`h-1.5 w-1.5 rounded-full bg-current ${status === "processing" ? "animate-pulse" : ""}`}
      />
      {s.label}
    </span>
  );
}
