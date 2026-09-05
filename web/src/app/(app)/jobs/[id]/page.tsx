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
  JobStatusBadge,
  PlanStatusBadge,
} from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import { getJob } from "@/lib/api/jobs";
import { listJobApplications } from "@/lib/api/applications";
import { listInterviews, getInterviewQuestionPlan, isQuestionPlanReady } from "@/lib/api/interviews";
import { getCandidate } from "@/lib/api/candidates";
import type {
  Application,
  Candidate,
  Interview,
  Job,
  QuestionPlan,
  QuestionPlanNotReady,
} from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const [job, setJob] = useState<Job | null>(null);
  const [applications, setApplications] = useState<
    Array<Application & { candidate?: Candidate }>
  >([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [plan, setPlan] = useState<QuestionPlan | QuestionPlanNotReady | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const jobRow = await getJob(jobId);
      const apps = await listJobApplications(jobId);
      const enriched = await Promise.all(
        apps.map(async (app) => ({
          ...app,
          candidate: await getCandidate(app.candidate_id),
        })),
      );
      const allInterviews = await listInterviews(jobRow.organization_id);
      const related = allInterviews.filter((item) =>
        apps.some((app) => app.id === item.application_id),
      );
      setJob(jobRow);
      setApplications(enriched);
      setInterviews(related);
      if (related[0]) {
        setPlan(await getInterviewQuestionPlan(related[0].id));
      } else {
        setPlan(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load job");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  if (loading) return <PageSkeleton />;
  if (error || !job) {
    return <ErrorState description={error || "Job not found"} onRetry={load} />;
  }

  return (
    <div>
      <PageHeader
        title={job.title}
        description={[job.department, job.location, job.employment_type]
          .filter(Boolean)
          .join(" · ")}
      >
        <JobStatusBadge status={job.status} />
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                {job.description || "No description provided."}
              </p>
              <p className="mt-4 text-xs text-muted-foreground">
                Updated {formatDate(job.updated_at)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Candidates</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {applications.length === 0 ? (
                <EmptyState
                  title="No candidates for this role"
                  description="Candidates linked through applications will appear here."
                />
              ) : (
                applications.map((app) => (
                  <Link
                    key={app.id}
                    href={`/candidates/${app.candidate_id}`}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-3 hover:bg-muted/40"
                  >
                    <div>
                      <div className="text-sm font-medium">
                        {app.candidate?.full_name || "Candidate"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {app.candidate?.email}
                      </div>
                    </div>
                    <ApplicationStatusBadge status={app.status} />
                  </Link>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Interview setup</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Interviews</span>
                <span className="font-medium tabular-nums">{interviews.length}</span>
              </div>
              {interviews[0] ? (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Latest status</span>
                  <InterviewStatusBadge status={interviews[0].status} />
                </div>
              ) : null}
              {!plan ? (
                <p className="text-muted-foreground">
                  Interview plan has not been generated yet.
                </p>
              ) : isQuestionPlanReady(plan) ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Plan</span>
                    <PlanStatusBadge status={plan.status} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Version {plan.version} · {plan.questions.length} questions
                  </p>
                  <Link
                    href={`/interviews/${plan.interview_id}`}
                    className="font-medium text-primary"
                  >
                    Review interview plan
                  </Link>
                </div>
              ) : (
                <p className="text-muted-foreground">{plan.detail}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
