"use client";

import { useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import type { AiEngineInfo } from "@/types/project";

export type EngineState = "checking" | "ready" | "rate_limited" | "offline";

export interface AiEngine {
  state: EngineState;
  /** Seconds until the soonest key frees up, when rate limited. */
  retryAfterSeconds: number | null;
  keysAvailable: number;
  keysTotal: number;
}

const INITIAL: AiEngine = {
  state: "checking",
  retryAfterSeconds: null,
  keysAvailable: 0,
  keysTotal: 0,
};

// Module-level so the sidebar, the campaign panel and the score card all read
// one shared truth from a single poller instead of three competing ones.
let current: AiEngine = INITIAL;
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function publish(next: AiEngine) {
  current = next;
  listeners.forEach((fn) => fn());
}

function fromInfo(ai: AiEngineInfo | undefined): AiEngine {
  if (!ai) {
    return { state: "ready", retryAfterSeconds: null, keysAvailable: 0, keysTotal: 0 };
  }
  return {
    state: ai.rate_limited ? "rate_limited" : "ready",
    retryAfterSeconds: ai.retry_after_seconds,
    keysAvailable: ai.keys_available,
    keysTotal: ai.keys_total,
  };
}

export async function refreshAiEngine(): Promise<AiEngine> {
  try {
    const res = await api.health();
    const next = fromInfo(res.ai);
    publish(next);
    return next;
  } catch {
    const next = { ...INITIAL, state: "offline" as const };
    publish(next);
    return next;
  }
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  // First subscriber starts the shared poll; the last one stops it.
  if (listeners.size === 1) {
    refreshAiEngine();
    timer = setInterval(refreshAiEngine, 20000);
  }
  return () => {
    listeners.delete(onChange);
    if (listeners.size === 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

/**
 * Live view of the AI engine's capacity, shared across the whole app.
 *
 * useSyncExternalStore is the right primitive here: the source of truth lives
 * outside React, and the server render must be the neutral "checking" state so
 * hydration matches.
 */
export function useAiEngine(): AiEngine {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => INITIAL,
  );
}

/** "16 min" / "45 sec" — a wait a person can act on. */
export function formatRetry(seconds: number | null): string {
  if (seconds == null || seconds <= 0) return "shortly";
  if (seconds < 90) return `${Math.ceil(seconds)} sec`;
  return `${Math.ceil(seconds / 60)} min`;
}
