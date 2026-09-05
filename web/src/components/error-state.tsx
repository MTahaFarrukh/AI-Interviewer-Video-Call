import { AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
}: {
  title?: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3 py-10">
        <div className="flex items-center gap-2 text-danger">
          <AlertCircle className="h-4 w-4" />
          <h3 className="text-sm font-semibold">{title}</h3>
        </div>
        <p className="max-w-xl text-sm text-muted-foreground">{description}</p>
        {onRetry ? (
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
