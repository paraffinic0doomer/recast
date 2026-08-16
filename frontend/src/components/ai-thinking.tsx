"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { ProjectStatus } from "@/types/project";

/**
 * What RECAST says while it works.
 *
 * Written in the first person and in the user's terms — "Listening to your
 * video" rather than "transcribing_audio". Each status cycles through its own
 * lines so a long stage never looks frozen, which is the single most useful
 * thing a live demo can show.
 */
const LINES: Partial<Record<ProjectStatus, string[]>> = {
  processing: [
    "Reading your video…",
    "Separating the audio track…",
    "Measuring resolution and pacing…",
  ],
  transcribing: [
    "Listening to your video…",
    "Writing down every word with timestamps…",
    "Catching the last few sentences…",
  ],
  transcribed: ["Transcript complete — starting to read it…"],
  analyzing: [
    "Understanding what this is really about…",
    "Analyzing your audience…",
    "Picking up on tone and intent…",
    "Distilling the core message…",
  ],
  analyzed: ["Content understood — looking for the highlights…"],
  detecting_moments: [
    "Finding the strongest moments…",
    "Scoring each segment for hook strength…",
    "Ranking what would work as a short…",
  ],
  generating: [
    "Adapting tone for TikTok…",
    "Writing a hook that earns the first three seconds…",
    "Tightening the LinkedIn opener…",
    "Fitting the thought into 280 characters…",
    "Building your YouTube chapters…",
  ],
};

const ROTATE_MS = 2600;

export function useAiLines(status: ProjectStatus): string | null {
  const lines = LINES[status];
  const [index, setIndex] = useState(0);
  const [seenStatus, setSeenStatus] = useState(status);

  // Restart the cycle whenever the pipeline moves to a new stage. Adjusting
  // during render (rather than in an effect) is React's documented pattern for
  // state derived from props, and avoids a wasted second render.
  if (seenStatus !== status) {
    setSeenStatus(status);
    setIndex(0);
  }

  useEffect(() => {
    if (!lines || lines.length < 2) return;
    const id = setInterval(
      () => setIndex((i) => (i + 1) % lines.length),
      ROTATE_MS,
    );
    return () => clearInterval(id);
  }, [lines]);

  if (!lines?.length) return null;
  return lines[index % lines.length];
}

/** Three drifting dots — the smallest possible "still working" signal. */
export function ThinkingDots({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)} aria-hidden>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1 rounded-full bg-current opacity-70 ai-pulse"
          style={{ animationDelay: `${i * 220}ms` }}
        />
      ))}
    </span>
  );
}

/**
 * Live status line for an actively-running project. Statuses without their own
 * script (a queued upload, say) fall back to the caller's plain description, so
 * a running stage is never left without a line.
 */
export function AiThinking({
  status,
  fallback,
  className,
}: {
  status: ProjectStatus;
  fallback?: string;
  className?: string;
}) {
  const line = useAiLines(status) ?? fallback;
  if (!line) return null;

  return (
    <p
      aria-live="polite"
      className={cn("flex items-center gap-2 text-sm text-primary", className)}
    >
      <ThinkingDots />
      <span className="min-w-0">{line}</span>
    </p>
  );
}
