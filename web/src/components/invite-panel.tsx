"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  createInterviewInvite,
  getInterviewInvite,
  regenerateInterviewInvite,
  revokeInterviewInvite,
} from "@/lib/api/invites";
import type { InviteCreated, InviteRead } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";
import { getInviteStatus } from "@/lib/status";
import { useAuth } from "@/lib/auth";

export function InvitePanel({ interviewId }: { interviewId: string }) {
  const { organization } = useAuth();
  const orgId = organization?.id;
  const [invite, setInvite] = useState<InviteRead | null>(null);
  const [created, setCreated] = useState<InviteCreated | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const row = await getInterviewInvite(interviewId, orgId);
      setInvite(row);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setInvite(null);
      } else {
        setError(err instanceof ApiError ? err.detail : "Failed to load invite");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewId, orgId]);

  async function createInvite() {
    setBusy(true);
    setError(null);
    try {
      const result = await createInterviewInvite(interviewId, 72, orgId);
      setCreated(result);
      setInvite(result.invite);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create invite");
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    setBusy(true);
    setError(null);
    try {
      const result = await regenerateInterviewInvite(interviewId, 72, orgId);
      setCreated(result);
      setInvite(result.invite);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to regenerate invite");
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    setBusy(true);
    setError(null);
    try {
      const result = await revokeInterviewInvite(interviewId, orgId);
      setInvite(result);
      setCreated(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to revoke invite");
    } finally {
      setBusy(false);
    }
  }

  function inviteAbsoluteUrl(path: string) {
    if (typeof window === "undefined") return path;
    return `${window.location.origin}${path}`;
  }

  async function copyLink() {
    if (!created) return;
    await navigator.clipboard.writeText(inviteAbsoluteUrl(created.invite_url_path));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Candidate invite</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {loading ? <p className="text-muted-foreground">Loading invite…</p> : null}
        {!loading && !invite ? (
          <>
            <p className="text-muted-foreground">
              No invite yet. Create a secure link to share with the candidate.
              Email delivery is not integrated yet.
            </p>
            <Button disabled={busy} onClick={() => void createInvite()}>
              Invite candidate
            </Button>
          </>
        ) : null}
        {invite ? (
          <>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Candidate journey</span>
              <Badge tone={getInviteStatus(invite.status).tone}>
                {getInviteStatus(invite.status).label}
              </Badge>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Expires</span>
              <span>{formatDate(invite.expires_at)}</span>
            </div>
            {created ? (
              <div className="rounded-xl border border-border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">{created.share_note}</div>
                <div className="mt-2 break-all font-mono text-xs">
                  {inviteAbsoluteUrl(created.invite_url_path)}
                </div>
                <Button
                  className="mt-3"
                  size="sm"
                  variant="secondary"
                  onClick={() => void copyLink()}
                >
                  {copied ? "Copied" : "Copy invite link"}
                </Button>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                The raw invite URL is only shown when you create or regenerate it.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void regenerate()}
              >
                Regenerate
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy || invite.status === "revoked"}
                onClick={() => void revoke()}
              >
                Revoke
              </Button>
            </div>
          </>
        ) : null}
        {error ? <p className="text-danger">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
