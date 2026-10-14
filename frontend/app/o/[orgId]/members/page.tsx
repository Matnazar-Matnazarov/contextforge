"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { useOrg } from "@/components/org-context";
import { Alert, Button, Card, Field, PageHeader, Select, Spinner } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { useMemberMutations, useMembers } from "@/lib/queries";
import { addMemberSchema } from "@/lib/schemas";
import type { Role } from "@/lib/types";

export default function MembersPage() {
  const { org, role } = useOrg();
  const members = useMembers(org.id);
  const { add, changeRole, remove } = useMemberMutations(org.id);
  const isOwner = role === "owner";
  const canManage = role === "owner" || role === "admin";
  const { register, handleSubmit, reset, formState: { errors } } = useForm<z.infer<typeof addMemberSchema>>({
    resolver: zodResolver(addMemberSchema),
    defaultValues: { role: "member" },
  });

  const mutationError = add.error ?? changeRole.error ?? remove.error;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <PageHeader title="Members" />
      {members.isLoading && <Spinner label="Loading members…" />}
      {members.isError && <Alert>{errorMessage(members.error)}</Alert>}
      {mutationError && <div className="mb-4"><Alert>{errorMessage(mutationError)}</Alert></div>}

      {members.data && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <caption className="sr-only">Members of {org.name}</caption>
            <thead className="bg-surface2 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5">Member</th>
                <th scope="col" className="px-4 py-2.5">Role</th>
                <th scope="col" className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {members.data.map((m) => {
                const removable = isOwner || (canManage && m.role === "member");
                return (
                  <tr key={m.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium">{m.display_name || m.email}</p>
                      {m.display_name && <p className="text-xs text-muted">{m.email}</p>}
                    </td>
                    <td className="px-4 py-3">
                      {isOwner ? (
                        <select
                          aria-label={`Role for ${m.email}`}
                          value={m.role}
                          onChange={(e) => changeRole.mutate({ id: m.id, role: e.target.value as Role })}
                          className="rounded-lg border border-line bg-surface px-2 py-1 text-sm"
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                          <option value="owner">Owner</option>
                        </select>
                      ) : (
                        <span className="capitalize">{m.role}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {removable && (
                        <Button variant="danger" aria-label={`Remove ${m.email}`} onClick={() => { if (confirm(`Remove ${m.email}?`)) remove.mutate(m.id); }}>
                          Remove
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {canManage ? (
        <Card>
          <h2 className="mb-1 font-semibold">Add a member</h2>
          <p className="mb-4 text-sm text-muted">The person must already have an account. Enter the email they registered with.</p>
          <form
            className="grid gap-3 sm:grid-cols-[1fr_10rem_auto] sm:items-end"
            onSubmit={handleSubmit(async (v) => { await add.mutateAsync(v).then(() => reset({ role: "member", email: "" })).catch(() => undefined); })}
            noValidate
          >
            <Field label="Email" type="email" error={errors.email?.message} {...register("email")} />
            <Select label="Role" {...register("role")}>
              <option value="member">Member</option>
              {isOwner && <option value="admin">Admin</option>}
              {isOwner && <option value="owner">Owner</option>}
            </Select>
            <Button type="submit" loading={add.isPending}>Add</Button>
          </form>
        </Card>
      ) : (
        <p className="text-sm text-muted">Only owners and admins can manage members.</p>
      )}
    </div>
  );
}
