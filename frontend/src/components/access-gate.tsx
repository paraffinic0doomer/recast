"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import Image from "next/image";
import { Lock, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_URL } from "@/lib/api";
import { getAccessKey, setAccessKey, subscribeAccessKey } from "@/lib/access";

type Check = "checking" | "open" | "locked";

/**
 * Blocks the workspace until a valid access key is supplied.
 *
 * Only shown when the backend is actually gated: an instance running on
 * localhost with no ACCESS_KEY set never sees this, so local development is
 * unaffected. On a publicly reachable instance it is what stops a stranger
 * from listing projects and downloading the owner's source videos.
 */
export function AccessGate({ children }: { children: React.ReactNode }) {
  const key = useSyncExternalStore(
    subscribeAccessKey,
    getAccessKey,
    () => "", // server render: assume no key, the client corrects immediately
  );

  const [check, setCheck] = useState<Check>("checking");
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // One unauthenticated probe tells us whether this backend is gated at all.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/projects`, {
      headers: { "bypass-tunnel-reminder": "true" },
    })
      .then((res) => {
        if (cancelled) return;
        setCheck(res.status === 401 ? "locked" : "open");
      })
      .catch(() => !cancelled && setCheck("open")); // offline: let the app show its own error
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const candidate = input.trim();
      if (!candidate) return;

      setSubmitting(true);
      setError(null);
      try {
        // Verify before storing, so a wrong key never half-loads the app.
        const res = await fetch(`${API_URL}/api/projects`, {
          headers: {
            "bypass-tunnel-reminder": "true",
            "X-Access-Key": candidate,
          },
        });
        if (res.status === 401) {
          setError("That key was not accepted.");
          return;
        }
        if (!res.ok) {
          setError(`The API responded with ${res.status}. Try again shortly.`);
          return;
        }
        setAccessKey(candidate);
      } catch {
        setError("Could not reach the API. Is the backend running?");
      } finally {
        setSubmitting(false);
      }
    },
    [input],
  );

  if (check === "checking") {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (check === "open" || key) return <>{children}</>;

  return (
    <main className="flex min-h-dvh items-center justify-center px-6 py-16">
      <div className="w-full max-w-sm space-y-8">
        <div className="flex flex-col items-center gap-4 text-center">
          <Image
            src="/recast-mark.png"
            alt=""
            width={56}
            height={56}
            className="size-12 invert dark:invert-0"
            priority
          />
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">RECAST</h1>
            <p className="text-sm text-muted-foreground">
              This workspace is private. Enter the access key to continue.
            </p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div className="relative">
            <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="password"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Access key"
              aria-label="Access key"
              autoFocus
              className="pl-9"
            />
          </div>

          {error && (
            <p className="flex items-start gap-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" size="lg" disabled={submitting || !input.trim()}>
            {submitting ? <Loader2 className="size-4 animate-spin" /> : <Lock className="size-4" />}
            {submitting ? "Checking…" : "Unlock workspace"}
          </Button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          Uploaded videos and generated clips are only visible to people with
          this key.
        </p>
      </div>
    </main>
  );
}
