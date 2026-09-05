import { apiFetch } from "./client";
import type { Candidate } from "./types";

export function listCandidates(organizationId: string) {
  return apiFetch<Candidate[]>(
    `/api/v1/organizations/${organizationId}/candidates`,
  );
}

export function getCandidate(candidateId: string) {
  return apiFetch<Candidate>(`/api/v1/candidates/${candidateId}`);
}
