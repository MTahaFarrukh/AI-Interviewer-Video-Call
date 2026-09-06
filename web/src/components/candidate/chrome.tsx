"use client";

import Link from "next/link";

export function CandidateChrome({
  children,
  eyebrow,
}: {
  children: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#f4f4f5_0%,_#fafafa_42%,_#e4e4e7_100%)]">
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-4 py-6 sm:px-6">
        <header className="mb-8 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
              F
            </span>
            <div>
              <div className="text-sm font-semibold tracking-tight">FirstRound</div>
              {eyebrow ? (
                <div className="text-xs text-muted-foreground">{eyebrow}</div>
              ) : null}
            </div>
          </Link>
          <div className="text-xs text-muted-foreground">Candidate interview</div>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
