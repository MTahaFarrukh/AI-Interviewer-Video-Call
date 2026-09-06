"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CandidateChrome } from "@/components/candidate/chrome";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { acceptInviteConsent, getPublicInvite } from "@/lib/api/invites";
import type { PublicInvite } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

export default function InterviewLandingPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = params.token;
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getPublicInvite(token);
        if (!cancelled) {
          setInvite(data);
          setConsent(data.consent_accepted);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.detail : "This invitation is invalid.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function continueToSetup() {
    if (!invite?.can_begin_setup) return;
    setSubmitting(true);
    setError(null);
    try {
      if (!invite.consent_accepted) {
        if (!consent) {
          setError("Please confirm the interview disclosure to continue.");
          setSubmitting(false);
          return;
        }
        await acceptInviteConsent(token);
      }
      router.push(`/interview/${token}/setup`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to continue.");
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <CandidateChrome>
        <PageSkeleton />
      </CandidateChrome>
    );
  }

  if (error && !invite) {
    return (
      <CandidateChrome>
        <ErrorState title="Invitation unavailable" description={error} />
      </CandidateChrome>
    );
  }

  if (!invite) return null;

  const blocked = !invite.can_begin_setup;

  return (
    <CandidateChrome eyebrow={invite.organization_name}>
      <Card>
        <CardHeader>
          <p className="text-sm text-muted-foreground">{invite.organization_name}</p>
          <CardTitle className="text-2xl">{invite.job_title}</CardTitle>
          <p className="text-sm text-muted-foreground">
            Hello {invite.candidate_name}. You are invited to a FirstRound AI
            technical interview.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-muted/30 p-3">
              <div className="text-xs text-muted-foreground">Expected duration</div>
              <div className="mt-1 text-sm font-medium">
                About {Math.round(invite.expected_duration_seconds / 60)} minutes
              </div>
            </div>
            <div className="rounded-xl border border-border bg-muted/30 p-3">
              <div className="text-xs text-muted-foreground">Invite expires</div>
              <div className="mt-1 text-sm font-medium">
                {formatDate(invite.expires_at)}
              </div>
            </div>
          </div>

          <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">
            <p>
              You will speak with an AI interviewer over voice. A working
              microphone is required. The conversation is transcribed so the
              hiring team can review your answers with evidence.
            </p>
            <p>
              FirstRound stores interview transcripts for evaluation. This product
              path does not currently advertise separate video recording storage.
              Camera is optional. You will not see a hiring score after the
              session. This invite link is personal — do not share it.
            </p>
          </div>

          {invite.message ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {invite.message}
            </div>
          ) : null}

          {!blocked ? (
            <label className="flex items-start gap-3 rounded-xl border border-border p-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                disabled={invite.consent_accepted}
              />
              <span>
                I understand this is an AI-powered interview that uses my
                microphone audio, generates a transcript, and evaluates my
                responses for the hiring team.
              </span>
            </label>
          ) : null}

          {error ? <p className="text-sm text-danger">{error}</p> : null}

          <div className="flex flex-wrap gap-3">
            <Button
              disabled={blocked || submitting || (!consent && !invite.consent_accepted)}
              onClick={() => void continueToSetup()}
            >
              {blocked ? "Unavailable" : submitting ? "Continuing…" : "Check my setup"}
            </Button>
            {invite.invite_status === "completed" ? (
              <Button
                variant="secondary"
                onClick={() => router.push(`/interview/${token}/complete`)}
              >
                View completion
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>
      <p className="mt-4 text-center text-xs text-muted-foreground">
        For the best experience, use a laptop or desktop with Chrome or Edge.
      </p>
    </CandidateChrome>
  );
}
