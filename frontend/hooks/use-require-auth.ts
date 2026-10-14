"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useMe } from "@/lib/queries";

export function useRequireAuth() {
  const me = useMe();
  const router = useRouter();
  useEffect(() => {
    if (!me.isLoading && !me.data) router.replace("/login");
  }, [me.isLoading, me.data, router]);
  return me;
}
