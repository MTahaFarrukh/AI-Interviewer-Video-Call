import { apiFetch } from "./client";
import type { InviteCreated, InviteRead, PublicInvite, SessionStart } from "./types";

function orgHeaders(organizationId?: string): HeadersInit | undefined {
  if (!organizationId) return undefined;
  return { "X-Organization-Id": organizationId };
}

export function createInterviewInvite(
  interviewId: string,
  ttlHours = 72,
  organizationId?: string,
) {
  return apiFetch<InviteCreated>(`/api/v1/interviews/${interviewId}/invite`, {
    method: "POST",
    body: JSON.stringify({ ttl_hours: ttlHours }),
    headers: orgHeaders(organizationId),
  });
}

export function getInterviewInvite(interviewId: string, organizationId?: string) {
  return apiFetch<InviteRead>(`/api/v1/interviews/${interviewId}/invite`, {
    headers: orgHeaders(organizationId),
  });
}

export function regenerateInterviewInvite(
  interviewId: string,
  ttlHours = 72,
  organizationId?: string,
) {
  return apiFetch<InviteCreated>(
    `/api/v1/interviews/${interviewId}/invite/regenerate`,
    {
      method: "POST",
      body: JSON.stringify({ ttl_hours: ttlHours }),
      headers: orgHeaders(organizationId),
    },
  );
}

export function revokeInterviewInvite(interviewId: string, organizationId?: string) {
  return apiFetch<InviteRead>(
    `/api/v1/interviews/${interviewId}/invite/revoke`,
    {
      method: "POST",
      headers: orgHeaders(organizationId),
    },
  );
}

export function getPublicInvite(token: string) {
  return apiFetch<PublicInvite>(`/api/v1/public/interview-invites/${token}`);
}

export function acceptInviteConsent(token: string) {
  return apiFetch<PublicInvite>(
    `/api/v1/public/interview-invites/${token}/consent`,
    {
      method: "POST",
      body: JSON.stringify({ accepted: true }),
    },
  );
}

export function startInviteSession(token: string) {
  return apiFetch<SessionStart>(
    `/api/v1/public/interview-invites/${token}/session`,
    { method: "POST" },
  );
}

export function completeInviteSession(token: string) {
  return apiFetch<PublicInvite>(
    `/api/v1/public/interview-invites/${token}/complete`,
    { method: "POST" },
  );
}
