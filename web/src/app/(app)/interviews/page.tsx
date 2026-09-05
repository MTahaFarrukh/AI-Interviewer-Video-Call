"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { InterviewStatusBadge } from "@/components/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { listInterviews } from "@/lib/api/interviews";
import { listOrganizationApplications } from "@/lib/api/applications";
import { listCandidates } from "@/lib/api/candidates";
import { listJobs } from "@/lib/api/jobs";
import type {
  Application,
  Candidate,
  Interview,
  InterviewStatus,
  Job,
} from "@/lib/api/types";
import { formatDate, formatDuration } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";

export default function InterviewsPage() {
  const { organization } = useAuth();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState<"all" | InterviewStatus>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!organization) return;
    setLoading(true);
    setError(null);
    try {
      const [rows, apps, people, jobRows] = await Promise.all([
        listInterviews(organization.id),
        listOrganizationApplications(organization.id),
        listCandidates(organization.id),
        listJobs(organization.id),
      ]);
      setInterviews(rows);
      setApplications(apps);
      setCandidates(people);
      setJobs(jobRows);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load interviews");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organization?.id]);

  const rows = useMemo(() => {
    return interviews
      .filter((item) => status === "all" || item.status === status)
      .map((interview) => {
        const app = applications.find((item) => item.id === interview.application_id);
        const candidate = candidates.find((item) => item.id === app?.candidate_id);
        const job = jobs.find((item) => item.id === app?.job_id);
        return { interview, candidate, job };
      });
  }, [interviews, applications, candidates, jobs, status]);

  if (!organization || loading) return <PageSkeleton />;
  if (error) return <ErrorState description={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Interviews"
        description="Manage prepared and completed screening sessions"
      />
      <div className="mb-5">
        <select
          className="h-10 rounded-lg border border-border bg-card px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value as "all" | InterviewStatus)}
          aria-label="Filter interviews"
        >
          <option value="all">All statuses</option>
          <option value="ready">Ready</option>
          <option value="prepared">Prepared</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No interviews yet"
          description="Interviews appear after an application is prepared for screening."
        />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-border text-xs text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">Candidate</th>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th className="px-5 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ interview, candidate, job }) => (
                  <tr key={interview.id} className="border-b border-border/70">
                    <td className="px-5 py-4">
                      <Link
                        href={`/interviews/${interview.id}`}
                        className="font-medium hover:text-primary"
                      >
                        {candidate?.full_name || "Candidate"}
                      </Link>
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {job?.title || "—"}
                    </td>
                    <td className="px-5 py-4">
                      <InterviewStatusBadge status={interview.status} />
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {formatDuration(interview.duration_seconds)}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {formatDate(interview.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
