"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CandidateChrome } from "@/components/candidate/chrome";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import { getPublicInvite } from "@/lib/api/invites";
import type { PublicInvite } from "@/lib/api/types";

export default function InterviewCompletePage() {
  const params = useParams<{ token: string }>();
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getPublicInvite(params.token);
        if (!cancelled) setInvite(data);
      } catch {
        if (!cancelled) setInvite(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.token]);

  if (loading) {
    return (
      <CandidateChrome>
        <PageSkeleton />
      </CandidateChrome>
    );
  }

  return (
    <CandidateChrome eyebrow="Completed">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Interview complete</CardTitle>
          <p className="text-sm text-muted-foreground">
            Your responses have been submitted to the hiring team.
          </p>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="rounded-xl border border-border bg-muted/30 p-4">
            <div className="text-muted-foreground">Company</div>
            <div className="font-medium">
              {invite?.organization_name || "Hiring team"}
            </div>
            <div className="mt-3 text-muted-foreground">Role</div>
            <div className="font-medium">{invite?.job_title || "Interview"}</div>
            <div className="mt-3 text-muted-foreground">Status</div>
            <div className="font-medium">Completed</div>
          </div>
          <p className="text-muted-foreground">
            Scores and hiring recommendations are not shown to candidates.
          </p>
          <Link
            href="/"
            className="inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            Close
          </Link>
        </CardContent>
      </Card>
    </CandidateChrome>
  );
}
