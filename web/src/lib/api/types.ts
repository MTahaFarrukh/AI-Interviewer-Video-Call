export type JobStatus = "draft" | "active" | "closed" | "archived";
export type ApplicationStatus =
  | "invited"
  | "pending"
  | "interview_ready"
  | "interviewing"
  | "completed"
  | "rejected"
  | "hired";
export type InterviewStatus =
  | "draft"
  | "prepared"
  | "ready"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled";
export type QuestionPlanStatus = "generated" | "review" | "approved" | "superseded";
export type InviteStatus =
  | "pending"
  | "opened"
  | "accepted"
  | "completed"
  | "expired"
  | "revoked";

export type Organization = {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
};

export type Job = {
  id: string;
  organization_id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  description: string;
  status: JobStatus;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type Candidate = {
  id: string;
  organization_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  github_url: string | null;
  linkedin_url: string | null;
  resume_url: string | null;
  created_at: string;
  updated_at: string;
};

export type Application = {
  id: string;
  organization_id: string;
  job_id: string;
  candidate_id: string;
  status: ApplicationStatus;
  created_at: string;
  updated_at: string;
};

export type Interview = {
  id: string;
  organization_id: string;
  application_id: string;
  status: InterviewStatus;
  livekit_room_name: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  expected_duration_seconds: number;
  created_at: string;
  updated_at: string;
};

export type Question = {
  id: string;
  position: number;
  question_text: string;
  competency: string | null;
  difficulty: string | null;
  rationale: string | null;
  max_followups: number;
  metadata_json?: Record<string, unknown> | null;
};

export type QuestionPlan = {
  id: string;
  interview_id: string;
  version: number;
  status: QuestionPlanStatus;
  source: string | null;
  recruiter_approved_at: string | null;
  created_at: string;
  updated_at: string;
  questions: Question[];
};

export type QuestionPlanNotReady = {
  interview_id: string;
  status: "not_ready";
  detail: string;
};

export type JobCreateInput = {
  title: string;
  description?: string;
  department?: string | null;
  location?: string | null;
  employment_type?: string | null;
  status?: JobStatus;
};

export type InviteRead = {
  id: string;
  interview_id: string;
  status: InviteStatus;
  expires_at: string;
  opened_at: string | null;
  accepted_at: string | null;
  completed_at: string | null;
  consent_accepted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type InviteCreated = {
  invite: InviteRead;
  invite_url_path: string;
  raw_token: string;
  share_note: string;
};

export type PublicInvite = {
  invite_status: InviteStatus;
  can_begin_setup: boolean;
  can_enter_room: boolean;
  expires_at: string;
  candidate_name: string;
  organization_name: string;
  job_title: string;
  expected_duration_seconds: number;
  interview_status: InterviewStatus;
  consent_accepted: boolean;
  message: string | null;
};

export type SessionStart = {
  room_name: string;
  participant_identity: string;
  livekit_url: string;
  token: string;
  interview_id: string;
  expected_duration_seconds: number;
  questions_total: number | null;
};
