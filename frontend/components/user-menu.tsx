"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useMe } from "@/lib/queries";
import { Button } from "./ui";

export function UserMenu() {
  const me = useMe();
  const qc = useQueryClient();
  const router = useRouter();
  async function logout() {
    await api("/auth/logout/", { method: "POST" }).catch(() => undefined);
    qc.clear();
    router.replace("/login");
  }
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="hidden text-muted sm:inline">{me.data?.email}</span>
      <Button variant="secondary" onClick={logout}>Sign out</Button>
    </div>
  );
}
