import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3 py-12">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="max-w-lg text-sm text-muted-foreground">{description}</p>
        {actionLabel && actionHref ? (
          <Link
            href={actionHref}
            className="inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            {actionLabel}
          </Link>
        ) : null}
        {actionLabel && onAction && !actionHref ? (
          <Button onClick={onAction}>{actionLabel}</Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
