"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { api, errorMessage } from "@/lib/api";
import { keys } from "@/lib/queries";
import { loginSchema, registerSchema } from "@/lib/schemas";
import type { User } from "@/lib/types";
import { Alert, Button, Card, Field } from "./ui";

type Mode = "login" | "register";

export function AuthForm({ mode }: { mode: Mode }) {
  const schema = mode === "login" ? loginSchema : registerSchema;
  type Values = z.infer<typeof registerSchema>;
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) as never });
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const qc = useQueryClient();

  async function onSubmit(values: Values) {
    setError(null);
    try {
      const user = await api<User>(`/auth/${mode}/`, { method: "POST", json: values });
      qc.setQueryData(keys.me, user);
      router.replace("/orgs");
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <main id="main" className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <div className="mb-6 text-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-accent">AI Knowledge Hub</p>
        <h1 className="mt-2 text-2xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      </div>
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error && <Alert>{error}</Alert>}
          <Field label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
          {mode === "register" && (
            <Field label="Display name (optional)" autoComplete="name" error={errors.display_name?.message} {...register("display_name")} />
          )}
          <Field
            label="Password"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            hint={mode === "register" ? "At least 10 characters." : undefined}
            error={errors.password?.message}
            {...register("password")}
          />
          <Button type="submit" loading={isSubmitting} className="w-full">
            {mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm text-muted">
        {mode === "login" ? (
          <>
            New here? <Link href="/register" className="font-medium text-accent underline">Create an account</Link>
          </>
        ) : (
          <>
            Already registered? <Link href="/login" className="font-medium text-accent underline">Sign in</Link>
          </>
        )}
      </p>
    </main>
  );
}
