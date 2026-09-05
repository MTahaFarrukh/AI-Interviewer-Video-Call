import Link from "next/link";

export function MarketingHeader() {
  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
      <Link href="/" className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
          F
        </span>
        <span className="text-sm font-semibold tracking-tight">FirstRound</span>
      </Link>
      <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
        <Link href="/#how-it-works" className="hover:text-foreground">
          Product
        </Link>
        <Link href="/pricing" className="hover:text-foreground">
          Pricing
        </Link>
        <Link href="/login" className="hover:text-foreground">
          Log in
        </Link>
        <Link
          href="/signup"
          className="rounded-lg bg-primary px-3 py-2 font-medium text-primary-foreground hover:opacity-90"
        >
          Start interviewing
        </Link>
      </nav>
      <Link
        href="/signup"
        className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground md:hidden"
      >
        Start
      </Link>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>FirstRound · AI-powered technical screening</div>
        <div className="flex gap-4">
          <Link href="/pricing">Pricing</Link>
          <Link href="/login">Log in</Link>
          <Link href="/signup">Sign up</Link>
        </div>
      </div>
    </footer>
  );
}
