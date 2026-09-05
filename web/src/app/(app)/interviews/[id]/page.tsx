"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { StatCard } from "@/components/stat-card";
import { QuestionReviewCard } from "@/components/question-review-card";
import {
  InterviewStatusBadge,
  PlanStatusBadge,
} from "@/components/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import {
  getInterview,
  getInterviewQuestionPlan,
  isQuestionPlanReady,
} from "@/lib/api/interviews";
import { listOrganizationApplications } from "@/lib/api/applications";
import { getCandidate } from "@/lib/api/candidates";
import { getJob } from "@/lib/api/jobs";
import type {
  Candidate,
  Interview,
  Job,
  QuestionPlan,
  QuestionPlanNotReady,
} from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { formatDate, formatDuration } from "@/lib/utils";

export default function InterviewDetailPage() {
  const params = useParams<{ id: string }>();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [plan, setPlan] = useState<QuestionPlan | QuestionPlanNotReady | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const row = await getInterview(params.id);
      const apps = await listOrganizationApplications(row.organization_id);
      const app = apps.find((item) => item.id === row.application_id);
      const [person, role, questionPlan] = await Promise.all([
        app ? getCandidate(app.candidate_id) : Promise.resolve(null),
        app ? getJob(app.job_id) : Promise.resolve(null),
        getInterviewQuestionPlan(row.id),
      ]);
      setInterview(row);
      setCandidate(person);
      setJob(role);
      setPlan(questionPlan);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load interview");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  if (loading) return <PageSkeleton />;
  if (error || !interview) {
    return (
      <ErrorState description={error || "Interview not found"} onRetry={load} />
    );
  }

  const readyPlan = plan && isQuestionPlanReady(plan) ? plan : null;

  return (
    <div>
      <PageHeader
        title={candidate?.full_name || "Interview"}
        description={`${job?.title || "Role"} · updated ${formatDate(interview.updated_at)}`}
      >
        <InterviewStatusBadge status={interview.status} />
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Overall score" value="—" hint="Available after evaluation" />
        <StatCard label="Recommendation" value="—" hint="Not ready yet" />
        <StatCard
          label="Questions"
          value={readyPlan ? readyPlan.questions.length : "—"}
        />
        <StatCard
          label="Duration"
          value={formatDuration(interview.duration_seconds)}
        />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Question review</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {!plan || !readyPlan ? (
                <EmptyState
                  title="Interview plan has not been generated yet"
                  description="This page only reads per-interview database plans. It never uses the global question_plan.json file."
                />
              ) : (
                readyPlan.questions.map((question) => (
                  <QuestionReviewCard key={question.id} question={question} />
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Transcript</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-sm text-muted-foreground">
                Transcript timeline will appear here once live session turns are
                linked to SaaS interview entities.
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Plan status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {readyPlan ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <PlanStatusBadge status={readyPlan.status} />
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Version</span>
                    <span>{readyPlan.version}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Source</span>
                    <span>{readyPlan.source || "—"}</span>
                  </div>
                </>
              ) : (
                <p className="text-muted-foreground">
                  {plan && !isQuestionPlanReady(plan)
                    ? plan.detail
                    : "No plan available."}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Report</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              PDF download will be enabled when a report resource exists for this
              interview. No fake download is offered in Phase 2.
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
