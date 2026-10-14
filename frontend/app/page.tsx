"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Spinner } from "@/components/ui";
import { useMe } from "@/lib/queries";

export default function Home() {
  const { data, isLoading } = useMe();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading) router.replace(data ? "/orgs" : "/login");
  }, [data, isLoading, router]);
  return (
    <main id="main" className="flex min-h-screen items-center justify-center">
      <Spinner label="Loading…" />
    </main>
  );
}
