"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import {
  ApplicationStatusBadge,
  InterviewStatusBadge,
} from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import { getCandidate } from "@/lib/api/candidates";
import { listCandidateApplications } from "@/lib/api/applications";
import { listInterviews } from "@/lib/api/interviews";
import { getJob } from "@/lib/api/jobs";
import type { Application, Candidate, Interview, Job } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

const timeline = [
  "Added",
  "Invited",
  "Interview prepared",
  "Interview completed",
  "Reviewed",
];

export default function CandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [applications, setApplications] = useState<
    Array<Application & { job?: Job }>
  >([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const person = await getCandidate(params.id);
      const apps = await listCandidateApplications(params.id);
      const enriched = await Promise.all(
        apps.map(async (app) => ({ ...app, job: await getJob(app.job_id) })),
      );
      const all = await listInterviews(person.organization_id);
      setCandidate(person);
      setApplications(enriched);
      setInterviews(
        all.filter((item) => apps.some((app) => app.id === item.application_id)),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load candidate");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  if (loading) return <PageSkeleton />;
  if (error || !candidate) {
    return (
      <ErrorState description={error || "Candidate not found"} onRetry={load} />
    );
  }

  const primary = applications[0];

  return (
    <div>
      <PageHeader
        title={candidate.full_name}
        description={candidate.email}
      >
        {primary ? <ApplicationStatusBadge status={primary.status} /> : null}
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Candidate context</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Resume</span>
                <span>{candidate.resume_url || "Not uploaded"}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">GitHub</span>
                <span className="truncate">
                  {candidate.github_url || "Not provided"}
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">LinkedIn</span>
                <span className="truncate">
                  {candidate.linkedin_url || "Not provided"}
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Phone</span>
                <span>{candidate.phone || "—"}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Applications</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {applications.length === 0 ? (
                <EmptyState
                  title="No applications"
                  description="This candidate is not linked to a job yet."
                />
              ) : (
                applications.map((app) => (
                  <div
                    key={app.id}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium">
                        {app.job?.title || "Role"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Added {formatDate(app.created_at)}
                      </div>
                    </div>
                    <ApplicationStatusBadge status={app.status} />
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Application timeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {timeline.map((step, index) => (
                <div key={step} className="flex items-center gap-3 text-sm">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs">
                    {index + 1}
                  </span>
                  <span className="text-muted-foreground">{step}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Interviews</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {interviews.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No interviews linked yet.
                </p>
              ) : (
                interviews.map((interview) => (
                  <Link
                    key={interview.id}
                    href={`/interviews/${interview.id}`}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-3 hover:bg-muted/40"
                  >
                    <div className="text-sm font-medium">
                      {interview.id.slice(0, 8)}…
                    </div>
                    <InterviewStatusBadge status={interview.status} />
                  </Link>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
