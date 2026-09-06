import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { InterviewerStage } from "@/components/candidate/interviewer-stage";
import {
  formatQuestionProgress,
  resolveQuestionProgress,
} from "@/lib/interview/question-progress";
import { getInviteStatus } from "@/lib/status";

describe("InterviewerStage", () => {
  it("exposes avatar mode and presence for future Simli swap", () => {
    const { container } = render(
      <InterviewerStage mode="local" presence="listening" />,
    );
    const stage = container.querySelector("[data-avatar-mode='local']");
    expect(stage).toBeTruthy();
    expect(stage).toHaveAttribute("data-presence", "listening");
  });
});

describe("question progress adapter", () => {
  it("does not invent totals when engine has not supplied them", () => {
    expect(
      formatQuestionProgress(
        resolveQuestionProgress({ questionsTotal: null, questionIndex: 4 }),
      ),
    ).toBe("Interview in progress");
  });

  it("formats real totals from session metadata", () => {
    expect(
      formatQuestionProgress(
        resolveQuestionProgress({ questionsTotal: 12, questionIndex: 4 }),
      ),
    ).toBe("Question 4 of 12");
  });
});

describe("invite journey labels", () => {
  it("maps invite statuses for recruiter visibility", () => {
    expect(getInviteStatus("pending").label).toBe("Invite ready");
    expect(getInviteStatus("opened").label).toBe("Opened");
    expect(getInviteStatus("completed").label).toBe("Completed");
    expect(getInviteStatus("expired").label).toBe("Expired");
  });
});

describe("invite API helpers", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/public/interview-invites/bad")) {
          return new Response(JSON.stringify({ detail: "Invite not found" }), {
            status: 404,
          });
        }
        return new Response(
          JSON.stringify({
            invite_status: "pending",
            can_begin_setup: true,
            can_enter_room: false,
            expires_at: new Date().toISOString(),
            candidate_name: "Alex",
            organization_name: "Northwind Labs",
            job_title: "Junior AI Engineer",
            expected_duration_seconds: 480,
            interview_status: "ready",
            consent_accepted: false,
            message: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads public invite payload", async () => {
    const { getPublicInvite } = await import("@/lib/api/invites");
    const invite = await getPublicInvite("good-token");
    expect(invite.organization_name).toBe("Northwind Labs");
    expect(invite.can_begin_setup).toBe(true);
  });

  it("surfaces invalid invite errors", async () => {
    const { getPublicInvite } = await import("@/lib/api/invites");
    await expect(getPublicInvite("bad")).rejects.toMatchObject({
      status: 404,
    });
  });
});
