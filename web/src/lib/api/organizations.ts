import { apiFetch } from "./client";
import type { Organization } from "./types";

export function listOrganizations() {
  return apiFetch<Organization[]>("/api/v1/organizations");
}

export function getOrganization(organizationId: string) {
  return apiFetch<Organization>(`/api/v1/organizations/${organizationId}`);
}
