import Link from "next/link";
import { Badge } from "@/components/ui/badge";

export function ProductPreview() {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-muted-foreground">
            Interview review
          </div>
          <div className="text-sm font-semibold">Alex Candidate · Junior AI Engineer</div>
        </div>
        <Badge tone="warning">Borderline</Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-muted/40 p-3">
          <div className="text-xs text-muted-foreground">Overall</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">3.6</div>
        </div>
        <div className="rounded-xl border border-border bg-muted/40 p-3">
          <div className="text-xs text-muted-foreground">Questions</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">9/12</div>
        </div>
        <div className="rounded-xl border border-border bg-muted/40 p-3">
          <div className="text-xs text-muted-foreground">Duration</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">8:02</div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <div className="rounded-xl border border-border p-3">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-medium">Technical competence</span>
            <span className="tabular-nums text-muted-foreground">4/5</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full w-4/5 rounded-full bg-primary" />
          </div>
        </div>
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium">Evidence</div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            “I compared chunking strategies based on retrieval quality and
            context preservation…”
          </p>
        </div>
        <div className="flex items-center justify-between rounded-xl border border-border p-3 text-sm">
          <span>Question 4 of 12 · follow-up</span>
          <Link href="/signup" className="font-medium text-primary">
            Open dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
