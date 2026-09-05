import type {
  ApplicationStatus,
  InterviewStatus,
  JobStatus,
  QuestionPlanStatus,
} from "./api/types";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export type StatusMeta = {
  label: string;
  tone: Tone;
};

const jobStatus: Record<JobStatus, StatusMeta> = {
  draft: { label: "Draft", tone: "neutral" },
  active: { label: "Active", tone: "success" },
  closed: { label: "Closed", tone: "warning" },
  archived: { label: "Archived", tone: "neutral" },
};

const applicationStatus: Record<ApplicationStatus, StatusMeta> = {
  invited: { label: "Invited", tone: "info" },
  pending: { label: "Pending", tone: "neutral" },
  interview_ready: { label: "Interview ready", tone: "info" },
  interviewing: { label: "Interviewing", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  hired: { label: "Hired", tone: "success" },
};

const interviewStatus: Record<InterviewStatus, StatusMeta> = {
  draft: { label: "Draft", tone: "neutral" },
  prepared: { label: "Prepared", tone: "info" },
  ready: { label: "Ready", tone: "info" },
  in_progress: { label: "In progress", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

const planStatus: Record<QuestionPlanStatus, StatusMeta> = {
  generated: { label: "Generated", tone: "info" },
  review: { label: "In review", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  superseded: { label: "Superseded", tone: "neutral" },
};

export function getJobStatus(status: JobStatus) {
  return jobStatus[status];
}

export function getApplicationStatus(status: ApplicationStatus) {
  return applicationStatus[status];
}

export function getInterviewStatus(status: InterviewStatus) {
  return interviewStatus[status];
}

export function getPlanStatus(status: QuestionPlanStatus) {
  return planStatus[status];
}
