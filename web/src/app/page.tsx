import Link from "next/link";
import {
  MarketingFooter,
  MarketingHeader,
} from "@/components/marketing/chrome";
import { ProductPreview } from "@/components/marketing/product-preview";

const steps = [
  {
    title: "Create a role",
    body: "Add a job description and define the competencies you want assessed.",
  },
  {
    title: "Invite a candidate",
    body: "Send a focused interview link. Candidates complete a short system check and join.",
  },
  {
    title: "FirstRound interviews",
    body: "A real-time AI interviewer asks adaptive follow-ups grounded in resume, JD, and GitHub context.",
  },
  {
    title: "Review evidence",
    body: "Get competency scores, strengths, concerns, and transcript quotes you can defend.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <MarketingHeader />
      <main>
        <section className="mx-auto grid w-full max-w-6xl gap-10 px-4 pb-16 pt-10 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:pt-16">
          <div>
            <p className="text-sm font-medium text-primary">
              AI-powered technical screening
            </p>
            <h1 className="mt-3 max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
              Run the first technical interview automatically.
            </h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
              FirstRound reviews candidate context, conducts a real-time
              technical interview, asks adaptive follow-ups, and produces
              evidence-backed evaluation for your hiring team.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href="/signup"
                className="inline-flex h-11 items-center rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                Start interviewing
              </Link>
              <Link
                href="/dashboard"
                className="inline-flex h-11 items-center rounded-lg border border-border bg-card px-5 text-sm font-medium hover:bg-muted"
              >
                View demo
              </Link>
            </div>
          </div>
          <ProductPreview />
        </section>

        <section
          id="how-it-works"
          className="border-y border-border bg-card/60"
        >
          <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6">
            <h2 className="text-2xl font-semibold tracking-tight">
              How FirstRound works
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              A focused workflow from role creation to evidence-backed review.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {steps.map((step, index) => (
                <div
                  key={step.title}
                  className="rounded-xl border border-border bg-background p-5"
                >
                  <div className="text-xs font-medium text-muted-foreground">
                    Step {index + 1}
                  </div>
                  <h3 className="mt-2 text-sm font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {step.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-3">
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold">Adaptive interviewing</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Interviews react to shallow, strong, or evasive answers. Follow-ups
              stay capped and grounded in resume, job description, and GitHub
              evidence.
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold">Evidence, not vibes</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Every competency score is tied to transcript quotes. Strengths,
              concerns, and question-level evidence stay reviewable by recruiters.
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold">Built for recruiter control</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Human-in-the-loop question plan review lets your team approve, edit,
              or reject plans before a candidate ever joins the room.
            </p>
          </div>
        </section>

        <section className="border-t border-border bg-card/60">
          <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-4 px-4 py-14 sm:flex-row sm:items-center sm:px-6">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">
                Ready to screen with evidence?
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Open the demo workspace and explore the recruiter product shell.
              </p>
            </div>
            <Link
              href="/signup"
              className="inline-flex h-11 items-center rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Start interviewing
            </Link>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </div>
  );
}
