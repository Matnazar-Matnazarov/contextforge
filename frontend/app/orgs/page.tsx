"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { Alert, Button, Card, EmptyState, Field, Spinner } from "@/components/ui";
import { UserMenu } from "@/components/user-menu";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { errorMessage } from "@/lib/api";
import { useCreateOrg, useOrgs } from "@/lib/queries";
import { orgSchema } from "@/lib/schemas";

export default function OrgsPage() {
  const me = useRequireAuth();
  const orgs = useOrgs();
  const create = useCreateOrg();
  const router = useRouter();
  const { register, handleSubmit, reset, formState: { errors } } = useForm<z.infer<typeof orgSchema>>({
    resolver: zodResolver(orgSchema),
  });

  if (me.isLoading || !me.data) return <main className="flex min-h-screen items-center justify-center"><Spinner label="Loading…" /></main>;

  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your organizations</h1>
        <UserMenu />
      </div>
      {orgs.isLoading && <Spinner label="Loading organizations…" />}
      {orgs.isError && <Alert>{errorMessage(orgs.error)}</Alert>}
      {orgs.data && orgs.data.length === 0 && (
        <EmptyState title="No organizations yet">Create one below, or ask an owner to add you by email.</EmptyState>
      )}
      <ul className="mb-8 grid gap-3 sm:grid-cols-2">
        {orgs.data?.map((o) => (
          <li key={o.id}>
            <Link href={`/o/${o.id}/chat`} className="block rounded-xl border border-line bg-surface p-4 transition hover:border-accent">
              <span className="block font-medium">{o.name}</span>
              <span className="text-xs capitalize text-muted">{o.role}</span>
            </Link>
          </li>
        ))}
      </ul>
      <Card>
        <h2 className="mb-3 font-semibold">Create an organization</h2>
        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={handleSubmit(async (v) => {
            const org = await create.mutateAsync(v.name).catch(() => null);
            if (org) {
              reset();
              router.push(`/o/${org.id}/documents`);
            }
          })}
          noValidate
        >
          <div className="flex-1"><Field label="Name" error={errors.name?.message} {...register("name")} /></div>
          <Button type="submit" loading={create.isPending}>Create</Button>
        </form>
        {create.isError && <div className="mt-3"><Alert>{errorMessage(create.error)}</Alert></div>}
      </Card>
    </main>
  );
}
