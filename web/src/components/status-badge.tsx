import { Badge } from "@/components/ui/badge";
import {
  getApplicationStatus,
  getInterviewStatus,
  getJobStatus,
  getPlanStatus,
} from "@/lib/status";
import type {
  ApplicationStatus,
  InterviewStatus,
  JobStatus,
  QuestionPlanStatus,
} from "@/lib/api/types";

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const meta = getJobStatus(status);
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function ApplicationStatusBadge({
  status,
}: {
  status: ApplicationStatus;
}) {
  const meta = getApplicationStatus(status);
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function InterviewStatusBadge({ status }: { status: InterviewStatus }) {
  const meta = getInterviewStatus(status);
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function PlanStatusBadge({ status }: { status: QuestionPlanStatus }) {
  const meta = getPlanStatus(status);
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}
