"use client";

import { createContext, useContext } from "react";
import type { Organization, Role } from "@/lib/types";

export const OrgContext = createContext<{ org: Organization; role: Role } | null>(null);

export function useOrg() {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrg must be used within an organization workspace");
  return ctx;
}
