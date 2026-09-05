"use client";

import * as React from "react";
import { listOrganizations } from "@/lib/api/organizations";
import type { Organization } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

type AuthState = {
  ready: boolean;
  authenticated: boolean;
  email: string;
  fullName: string;
  organization: Organization | null;
  organizations: Organization[];
  error: string | null;
  enterDemo: () => Promise<void>;
  leaveDemo: () => void;
  setOrganizationId: (id: string) => void;
};

const AuthContext = React.createContext<AuthState | null>(null);

const STORAGE_KEY = "firstround.dev.auth";

type StoredAuth = {
  authenticated: boolean;
  organizationId?: string;
};

/**
 * Phase 2 development auth placeholder.
 * Replace with Supabase Auth in a later phase — keep identity logic here only.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = React.useState(false);
  const [authenticated, setAuthenticated] = React.useState(false);
  const [organizations, setOrganizations] = React.useState<Organization[]>([]);
  const [organization, setOrganization] = React.useState<Organization | null>(
    null,
  );
  const [error, setError] = React.useState<string | null>(null);

  const hydrate = React.useCallback(async (preferOrgId?: string) => {
    try {
      const orgs = await listOrganizations();
      setOrganizations(orgs);
      const preferredSlug =
        process.env.NEXT_PUBLIC_DEV_ORG_SLUG || "northwind-labs";
      const selected =
        orgs.find((org) => org.id === preferOrgId) ||
        orgs.find((org) => org.slug === preferredSlug) ||
        orgs[0] ||
        null;
      setOrganization(selected);
      setError(null);
      return selected;
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.detail
          : "Unable to reach the FirstRound API. Start the FastAPI server.";
      setError(message);
      setOrganizations([]);
      setOrganization(null);
      return null;
    }
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const stored: StoredAuth | null = raw ? JSON.parse(raw) : null;
      if (stored?.authenticated) {
        await hydrate(stored.organizationId);
        if (!cancelled) setAuthenticated(true);
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [hydrate]);

  const enterDemo = React.useCallback(async () => {
    const selected = await hydrate();
    setAuthenticated(true);
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        authenticated: true,
        organizationId: selected?.id,
      } satisfies StoredAuth),
    );
  }, [hydrate]);

  const leaveDemo = React.useCallback(() => {
    setAuthenticated(false);
    window.localStorage.removeItem(STORAGE_KEY);
  }, []);

  const setOrganizationId = React.useCallback(
    (id: string) => {
      const next = organizations.find((org) => org.id === id) || null;
      setOrganization(next);
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          authenticated: true,
          organizationId: next?.id,
        } satisfies StoredAuth),
      );
    },
    [organizations],
  );

  const value: AuthState = {
    ready,
    authenticated,
    email: "recruiter@northwind.local",
    fullName: "Northwind Recruiter",
    organization,
    organizations,
    error,
    enterDemo,
    leaveDemo,
    setOrganizationId,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
