import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actionLabel,
  actionHref,
  children,
  className,
}: {
  title: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        {children}
        {actionLabel && actionHref ? (
          <Link href={actionHref}>
            <Button>{actionLabel}</Button>
          </Link>
        ) : null}
      </div>
    </div>
  );
}
