import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Question } from "@/lib/api/types";

export function QuestionReviewCard({ question }: { question: Question }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Q{question.position}</CardTitle>
          {question.competency ? (
            <Badge tone="info">{question.competency}</Badge>
          ) : null}
          {question.difficulty ? (
            <Badge>{question.difficulty}</Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="leading-relaxed">{question.question_text}</p>
        {question.rationale ? (
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">Rationale: </span>
            {question.rationale}
          </p>
        ) : null}
        <div className="text-xs text-muted-foreground">
          Max follow-ups: {question.max_followups}
        </div>
        <div className="rounded-lg border border-dashed border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          Candidate answer, score, and evidence will appear here after evaluation
          is connected in a later phase.
        </div>
      </CardContent>
    </Card>
  );
}
