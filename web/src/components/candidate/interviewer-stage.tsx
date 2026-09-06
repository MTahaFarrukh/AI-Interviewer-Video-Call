"use client";

import { cn } from "@/lib/utils";

export type AvatarMode = "local" | "simli";
export type InterviewerPresence = "idle" | "listening" | "speaking" | "connecting";

/**
 * Interviewer stage abstraction.
 * Phase 3 uses local/placeholder rendering.
 * Phase 6 can swap in Simli video without rebuilding the room layout.
 */
export function InterviewerStage({
  mode = "local",
  presence = "idle",
  displayName = "FirstRound Interviewer",
  className,
}: {
  mode?: AvatarMode;
  presence?: InterviewerPresence;
  displayName?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex aspect-[4/5] w-full max-w-md flex-col items-center justify-end overflow-hidden rounded-3xl border border-border bg-gradient-to-b from-zinc-100 to-zinc-200 shadow-sm dark:from-zinc-900 dark:to-zinc-950",
        className,
      )}
      data-avatar-mode={mode}
      data-presence={presence}
      aria-label={`${displayName} is ${presence}`}
    >
      <div
        className={cn(
          "absolute inset-0 transition-opacity duration-500",
          presence === "speaking" && "opacity-100",
          presence === "listening" && "opacity-80",
          presence === "idle" && "opacity-60",
          presence === "connecting" && "opacity-40",
        )}
        style={{
          background:
            "radial-gradient(circle at 50% 35%, rgba(79,70,229,0.18), transparent 55%)",
        }}
      />
      <div className="relative mb-16 flex h-40 w-40 items-center justify-center rounded-full border border-white/70 bg-white/80 shadow-lg backdrop-blur">
        <div
          className={cn(
            "h-24 w-24 rounded-full bg-zinc-800 transition-transform duration-300",
            presence === "speaking" && "scale-105",
          )}
        />
        <div
          className={cn(
            "absolute bottom-8 h-2 rounded-full bg-zinc-500 transition-all duration-150",
            presence === "speaking" ? "w-10" : "w-6",
            presence === "listening" && "w-7 bg-emerald-500",
          )}
        />
      </div>
      <div className="absolute bottom-4 left-4 right-4 rounded-xl border border-white/60 bg-white/80 px-3 py-2 text-sm backdrop-blur">
        <div className="font-medium">{displayName}</div>
        <div className="text-xs capitalize text-muted-foreground">{presence}</div>
      </div>
    </div>
  );
}
