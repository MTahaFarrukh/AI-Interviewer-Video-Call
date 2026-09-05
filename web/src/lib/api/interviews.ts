import { ApiError, apiFetch } from "./client";
import type {
  Interview,
  QuestionPlan,
  QuestionPlanNotReady,
} from "./types";

export function listInterviews(organizationId: string) {
  return apiFetch<Interview[]>(
    `/api/v1/organizations/${organizationId}/interviews`,
  );
}

export function getInterview(interviewId: string) {
  return apiFetch<Interview>(`/api/v1/interviews/${interviewId}`);
}

export async function getInterviewQuestionPlan(interviewId: string) {
  try {
    return await apiFetch<QuestionPlan>(
      `/api/v1/interviews/${interviewId}/question-plan`,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return {
        interview_id: interviewId,
        status: "not_ready",
        detail: error.detail || "Interview plan has not been generated yet.",
      } satisfies QuestionPlanNotReady;
    }
    throw error;
  }
}

export function isQuestionPlanReady(
  plan: QuestionPlan | QuestionPlanNotReady,
): plan is QuestionPlan {
  return !("status" in plan && plan.status === "not_ready");
}
