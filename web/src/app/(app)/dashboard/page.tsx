"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { InterviewStatusBadge, JobStatusBadge } from "@/components/status-badge";
import { useAuth } from "@/lib/auth";
import { listJobs } from "@/lib/api/jobs";
import { listCandidates } from "@/lib/api/candidates";
import { listInterviews } from "@/lib/api/interviews";
import type { Candidate, Interview, Job } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";

export default function DashboardPage() {
  const { organization } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!organization) return;
    setLoading(true);
    setError(null);
    try {
      const [jobRows, candidateRows, interviewRows] = await Promise.all([
        listJobs(organization.id),
        listCandidates(organization.id),
        listInterviews(organization.id),
      ]);
      setJobs(jobRows);
      setCandidates(candidateRows);
      setInterviews(interviewRows);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organization?.id]);

  if (!organization || loading) return <PageSkeleton />;
  if (error) return <ErrorState description={error} onRetry={load} />;

  const activeJobs = jobs.filter((job) => job.status === "active");
  const completed = interviews.filter((item) => item.status === "completed");
  const recent = interviews.slice(0, 5);

  return (
    <div>
      <PageHeader
        title="Hiring overview"
        description={`${organization.name} · recruiter workspace`}
        actionLabel="Create job"
        actionHref="/jobs/new"
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active jobs" value={activeJobs.length} />
        <StatCard label="Candidates" value={candidates.length} />
        <StatCard label="Interviews" value={interviews.length} />
        <StatCard label="Completed" value={completed.length} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Recent interviews</CardTitle>
          </CardHeader>
          <CardContent>
            {recent.length === 0 ? (
              <EmptyState
                title="No interviews yet"
                description="Create a job and prepare an interview to see activity here."
                actionLabel="Create job"
                actionHref="/jobs/new"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-left text-sm">
                  <thead className="text-xs text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="pb-2 font-medium">Interview</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Updated</th>
                      <th className="pb-2 font-medium" />
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((interview) => (
                      <tr key={interview.id} className="border-b border-border/70">
                        <td className="py-3">
                          <div className="font-medium">
                            {interview.id.slice(0, 8)}…
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Application {interview.application_id.slice(0, 8)}…
                          </div>
                        </td>
                        <td className="py-3">
                          <InterviewStatusBadge status={interview.status} />
                        </td>
                        <td className="py-3 text-muted-foreground">
                          {formatDate(interview.updated_at)}
                        </td>
                        <td className="py-3 text-right">
                          <Link
                            href={`/interviews/${interview.id}`}
                            className="font-medium text-primary"
                          >
                            Open
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Active jobs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeJobs.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No active jobs. Draft roles appear on the Jobs page.
              </p>
            ) : (
              activeJobs.slice(0, 5).map((job) => (
                <Link
                  key={job.id}
                  href={`/jobs/${job.id}`}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-3 hover:bg-muted/50"
                >
                  <div>
                    <div className="text-sm font-medium">{job.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {job.location || "Remote / flexible"}
                    </div>
                  </div>
                  <JobStatusBadge status={job.status} />
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
