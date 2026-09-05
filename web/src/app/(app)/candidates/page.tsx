"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { ApplicationStatusBadge } from "@/components/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { listCandidates } from "@/lib/api/candidates";
import { listOrganizationApplications } from "@/lib/api/applications";
import { listJobs } from "@/lib/api/jobs";
import type { Application, Candidate, Job } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";

export default function CandidatesPage() {
  const { organization } = useAuth();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!organization) return;
    setLoading(true);
    setError(null);
    try {
      const [people, apps, jobRows] = await Promise.all([
        listCandidates(organization.id),
        listOrganizationApplications(organization.id),
        listJobs(organization.id),
      ]);
      setCandidates(people);
      setApplications(apps);
      setJobs(jobRows);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load candidates");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organization?.id]);

  const rows = useMemo(() => {
    return candidates
      .map((candidate) => {
        const app = applications.find((item) => item.candidate_id === candidate.id);
        const job = jobs.find((item) => item.id === app?.job_id);
        return { candidate, app, job };
      })
      .filter(({ candidate }) => {
        const q = query.trim().toLowerCase();
        if (!q) return true;
        return (
          candidate.full_name.toLowerCase().includes(q) ||
          candidate.email.toLowerCase().includes(q)
        );
      });
  }, [candidates, applications, jobs, query]);

  if (!organization || loading) return <PageSkeleton />;
  if (error) return <ErrorState description={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Candidates"
        description="People in your organization pipeline"
      />
      <div className="mb-5">
        <Input
          placeholder="Search candidates"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search candidates"
        />
      </div>
      {rows.length === 0 ? (
        <EmptyState
          title="No candidates yet"
          description="Seeded or invited candidates will appear in this list."
        />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-border text-xs text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">Candidate</th>
                  <th className="px-5 py-3 font-medium">Role</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Added</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ candidate, app, job }) => (
                  <tr key={candidate.id} className="border-b border-border/70">
                    <td className="px-5 py-4">
                      <Link
                        href={`/candidates/${candidate.id}`}
                        className="font-medium hover:text-primary"
                      >
                        {candidate.full_name}
                      </Link>
                      <div className="text-xs text-muted-foreground">
                        {candidate.email}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {job?.title || "—"}
                    </td>
                    <td className="px-5 py-4">
                      {app ? (
                        <ApplicationStatusBadge status={app.status} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {formatDate(candidate.created_at)}
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
