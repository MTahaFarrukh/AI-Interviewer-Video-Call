import { describe, expect, it } from "vitest";
import {
  getApplicationStatus,
  getInterviewStatus,
  getJobStatus,
} from "@/lib/status";
import { cn, formatDuration } from "@/lib/utils";

describe("status helpers", () => {
  it("maps job statuses", () => {
    expect(getJobStatus("active").label).toBe("Active");
    expect(getJobStatus("draft").tone).toBe("neutral");
  });

  it("maps application and interview statuses", () => {
    expect(getApplicationStatus("interview_ready").label).toBe("Interview ready");
    expect(getInterviewStatus("in_progress").tone).toBe("warning");
  });
});

describe("utils", () => {
  it("merges class names", () => {
    expect(cn("px-2", false && "hidden", "text-sm")).toContain("px-2");
  });

  it("formats duration", () => {
    expect(formatDuration(125)).toBe("2m 05s");
    expect(formatDuration(null)).toBe("—");
  });
});
