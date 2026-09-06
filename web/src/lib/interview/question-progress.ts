/**
 * Temporary question-progress adapter for the candidate room.
 *
 * Phase 3: prefer session.questions_total from the public session API
 * (DB plan count when present). Live index updates arrive via LiveKit data
 * packets (`type: "interview_ui"`) when the engine publishes them.
 *
 * Do NOT import or fetch global `question_plan.json` from the Next.js app.
 * Phase 4+ should replace this with engine-bound SaaS session metadata.
 */

export type QuestionProgress = {
  current: number;
  total: number | null;
};

export function resolveQuestionProgress(input: {
  questionsTotal: number | null | undefined;
  questionIndex: number;
}): QuestionProgress {
  const total =
    typeof input.questionsTotal === "number" && input.questionsTotal > 0
      ? input.questionsTotal
      : null;
  return {
    current: Math.max(1, input.questionIndex || 1),
    total,
  };
}

export function formatQuestionProgress(progress: QuestionProgress): string {
  if (progress.total == null) return "Interview in progress";
  return `Question ${progress.current} of ${progress.total}`;
}
