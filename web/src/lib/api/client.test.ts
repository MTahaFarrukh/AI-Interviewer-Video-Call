import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ApiError, apiFetch } from "@/lib/api/client";
import { isQuestionPlanReady } from "@/lib/api/interviews";

describe("api client", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Job not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws structured ApiError", async () => {
    await expect(apiFetch("/api/v1/jobs/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: "Job not found",
    } satisfies Partial<ApiError>);
  });
});

describe("question plan helpers", () => {
  it("detects not-ready plans", () => {
    expect(
      isQuestionPlanReady({
        interview_id: "x",
        status: "not_ready",
        detail: "missing",
      }),
    ).toBe(false);
  });
});
