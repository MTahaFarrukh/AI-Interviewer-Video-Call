import { apiFetch } from "./client";
import type { Job, JobCreateInput } from "./types";

export function listJobs(organizationId: string) {
  return apiFetch<Job[]>(`/api/v1/organizations/${organizationId}/jobs`);
}

export function getJob(jobId: string) {
  return apiFetch<Job>(`/api/v1/jobs/${jobId}`);
}

export function createJob(organizationId: string, payload: JobCreateInput) {
  return apiFetch<Job>(`/api/v1/organizations/${organizationId}/jobs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateJob(jobId: string, payload: Partial<JobCreateInput>) {
  return apiFetch<Job>(`/api/v1/jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
