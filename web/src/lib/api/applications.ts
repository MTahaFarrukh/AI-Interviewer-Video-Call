import { apiFetch } from "./client";
import type { Application } from "./types";

export function listOrganizationApplications(organizationId: string) {
  return apiFetch<Application[]>(
    `/api/v1/organizations/${organizationId}/applications`,
  );
}

export function listJobApplications(jobId: string) {
  return apiFetch<Application[]>(`/api/v1/jobs/${jobId}/applications`);
}

export function listCandidateApplications(candidateId: string) {
  return apiFetch<Application[]>(
    `/api/v1/candidates/${candidateId}/applications`,
  );
}
