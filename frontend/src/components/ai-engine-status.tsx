"use client";

import { cn } from "@/lib/utils";
import { useAiEngine, formatRetry } from "@/lib/use-ai-engine";

/**
 * Live backend status for the sidebar footer.
 *
 * This is a real health check, not decoration. It reports three things that
 * change what the user should do next: the API being down, every API key being
 * rate-limited (with the wait), and everything being fine.
 */
export function AiEngineStatus({ collapsed = false }: { collapsed?: boolean }) {
  const engine = useAiEngine();

  const copy = {
    checking: {
      label: "Connecting…",
      detail: null,
      tone: "text-muted-foreground",
      dot: "bg-muted-foreground",
    },
    ready: {
      label: "Ready",
      detail: null,
      tone: "text-success",
      dot: "bg-success",
    },
    rate_limited: {
      label: "Rate limited",
      detail: `Back in ${formatRetry(engine.retryAfterSeconds)}`,
      tone: "text-warning",
      dot: "bg-warning",
    },
    offline: {
      label: "Offline",
      detail: "Backend unreachable",
      tone: "text-destructive",
      dot: "bg-destructive",
    },
  }[engine.state];

  if (collapsed) {
    return (
      <span
        title={`AI Engine — ${copy.label}${copy.detail ? ` (${copy.detail})` : ""}`}
        className={cn(
          "size-2 rounded-full",
          copy.dot,
          engine.state === "ready" && "ai-pulse",
        )}
      />
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-2.5">
      <span className="relative flex size-2 shrink-0">
        {engine.state === "ready" && (
          <span className="absolute inline-flex size-full rounded-full bg-success opacity-60 ai-pulse" />
        )}
        <span className={cn("relative inline-flex size-2 rounded-full", copy.dot)} />
      </span>
      <div className="min-w-0 leading-tight">
        <p className="text-[0.6875rem] font-medium uppercase tracking-wider text-muted-foreground">
          AI Engine
        </p>
        <p className={cn("truncate text-sm font-medium", copy.tone)}>{copy.label}</p>
        {copy.detail && (
          <p className="truncate text-xs text-muted-foreground">{copy.detail}</p>
        )}
      </div>
    </div>
  );
}
