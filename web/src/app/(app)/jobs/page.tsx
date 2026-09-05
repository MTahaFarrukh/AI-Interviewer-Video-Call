"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { JobStatusBadge } from "@/components/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { listJobs } from "@/lib/api/jobs";
import { listJobApplications } from "@/lib/api/applications";
import type { Job, JobStatus } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";

export default function JobsPage() {
  const { organization } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | JobStatus>("all");

  async function load() {
    if (!organization) return;
    setLoading(true);
    setError(null);
    try {
      const rows = await listJobs(organization.id);
      setJobs(rows);
      const pairs = await Promise.all(
        rows.map(async (job) => {
          const apps = await listJobApplications(job.id);
          return [job.id, apps.length] as const;
        }),
      );
      setCounts(Object.fromEntries(pairs));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organization?.id]);

  const filtered = useMemo(() => {
    return jobs.filter((job) => {
      const matchesQuery = job.title
        .toLowerCase()
        .includes(query.trim().toLowerCase());
      const matchesStatus = status === "all" || job.status === status;
      return matchesQuery && matchesStatus;
    });
  }, [jobs, query, status]);

  if (!organization || loading) return <PageSkeleton />;
  if (error) return <ErrorState description={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Jobs"
        description="Roles your team is screening for"
        actionLabel="Create job"
        actionHref="/jobs/new"
      />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row">
        <Input
          placeholder="Search jobs"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search jobs"
        />
        <select
          className="h-10 rounded-lg border border-border bg-card px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value as "all" | JobStatus)}
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="closed">Closed</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No jobs yet"
          description="Create your first role to start inviting candidates and preparing interviews."
          actionLabel="Create job"
          actionHref="/jobs/new"
        />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-border text-xs text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">Role</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Candidates</th>
                  <th className="px-5 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((job) => (
                  <tr key={job.id} className="border-b border-border/70">
                    <td className="px-5 py-4">
                      <Link
                        href={`/jobs/${job.id}`}
                        className="font-medium hover:text-primary"
                      >
                        {job.title}
                      </Link>
                      <div className="text-xs text-muted-foreground">
                        {[job.department, job.location].filter(Boolean).join(" · ") ||
                          "No metadata"}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-5 py-4 tabular-nums">{counts[job.id] ?? 0}</td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {formatDate(job.updated_at)}
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
