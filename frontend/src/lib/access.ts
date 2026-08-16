"use client";

/**
 * Client-side storage for the API access key.
 *
 * The key is typed in by the operator and kept in localStorage rather than
 * baked into the bundle: anything in NEXT_PUBLIC_* ships to every visitor and
 * would not be a secret at all. This way a public deployment shows a gate,
 * and only someone given the key can reach the projects behind it.
 */

const STORAGE_KEY = "recast.access-key";

let cached: string | null = null;
const listeners = new Set<() => void>();

export function getAccessKey(): string {
  if (cached !== null) return cached;
  if (typeof window === "undefined") return "";
  cached = window.localStorage.getItem(STORAGE_KEY) ?? "";
  return cached;
}

export function setAccessKey(key: string): void {
  cached = key;
  if (typeof window !== "undefined") {
    if (key) window.localStorage.setItem(STORAGE_KEY, key);
    else window.localStorage.removeItem(STORAGE_KEY);
  }
  listeners.forEach((fn) => fn());
}

export function clearAccessKey(): void {
  setAccessKey("");
}

export function subscribeAccessKey(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
