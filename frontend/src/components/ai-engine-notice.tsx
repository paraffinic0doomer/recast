"use client";

import { Hourglass, PlugZap } from "lucide-react";
import { useAiEngine, formatRetry } from "@/lib/use-ai-engine";

/**
 * Explains, next to the buttons it affects, why generation cannot run.
 *
 * Without this the generate buttons appear to do nothing: the request succeeds,
 * the background task hits a 429, and the UI returns to the same empty state.
 * Renders nothing when the engine is healthy.
 */
export function AiEngineNotice() {
  const engine = useAiEngine();

  if (engine.state === "offline") {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/[0.06] px-4 py-3">
        <PlugZap className="size-4 shrink-0 text-destructive" />
        <p className="min-w-0 flex-1 text-sm text-foreground">
          <strong className="font-semibold">The API is unreachable.</strong>{" "}
          Generating won&apos;t work until the backend is running again.
        </p>
      </div>
    );
  }

  if (engine.state !== "rate_limited") return null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/[0.06] px-4 py-3">
      <Hourglass className="size-4 shrink-0 text-warning" />
      <p className="min-w-0 flex-1 text-sm text-foreground">
        <strong className="font-semibold">
          The AI engine has hit its daily token limit.
        </strong>{" "}
        All {engine.keysTotal} API keys are cooling down — generating will work
        again in about {formatRetry(engine.retryAfterSeconds)}. Everything
        already generated is saved.
      </p>
    </div>
  );
}
