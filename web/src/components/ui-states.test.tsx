import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { JobStatusBadge } from "@/components/status-badge";

describe("shared UI states", () => {
  it("renders empty state CTA", () => {
    render(
      <EmptyState
        title="No jobs yet"
        description="Create your first role."
        actionLabel="Create job"
        actionHref="/jobs/new"
      />,
    );
    expect(screen.getByText("No jobs yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create job" })).toHaveAttribute(
      "href",
      "/jobs/new",
    );
  });

  it("renders error state", () => {
    render(<ErrorState description="API unavailable" />);
    expect(screen.getByText("API unavailable")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<JobStatusBadge status="active" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });
});
