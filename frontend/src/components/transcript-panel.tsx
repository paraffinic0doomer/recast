"use client";

import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SectionHeader } from "@/components/workspace";
import { cn } from "@/lib/utils";
import type { Transcript } from "@/types/project";

export function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Splits text into matched/unmatched parts so hits can be highlighted. */
function highlight(text: string, query: string) {
  if (!query.trim()) return [{ text, match: false }];

  const parts: { text: string; match: boolean }[] = [];
  const lower = text.toLowerCase();
  const needle = query.toLowerCase();
  let cursor = 0;

  for (;;) {
    const idx = lower.indexOf(needle, cursor);
    if (idx === -1) break;
    if (idx > cursor) parts.push({ text: text.slice(cursor, idx), match: false });
    parts.push({ text: text.slice(idx, idx + needle.length), match: true });
    cursor = idx + needle.length;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), match: false });
  return parts;
}

interface TranscriptPanelProps {
  transcript: Transcript;
  /** Called with a timestamp in seconds when the user clicks a segment. */
  onSeek?: (seconds: number) => void;
  /** Currently playing time, used to highlight the active segment. */
  currentTime?: number;
}

export function TranscriptPanel({
  transcript,
  onSeek,
  currentTime = 0,
}: TranscriptPanelProps) {
  const [query, setQuery] = useState("");

  // Memoised so the `?? []` fallback doesn't produce a new array identity on
  // every render and invalidate the two memos below.
  const segments = useMemo(
    () => transcript.segments ?? [],
    [transcript.segments],
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return segments;
    const needle = query.toLowerCase();
    return segments.filter((s) => s.text.toLowerCase().includes(needle));
  }, [segments, query]);

  const activeIndex = useMemo(() => {
    return segments.findIndex(
      (s) => currentTime >= s.start && currentTime < s.end,
    );
  }, [segments, currentTime]);

  return (
    <section className="space-y-5">
      <SectionHeader
        title="Transcript"
        count={segments.length}
        description={
          transcript.language
            ? `Detected language: ${transcript.language.toUpperCase()}. Click any line to jump the video there.`
            : "Click any line to jump the video there."
        }
      />

      <div className="space-y-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search transcript…"
            aria-label="Search transcript"
            className="pl-9 pr-9"
          />
          {query && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setQuery("")}
              className="absolute right-1 top-1/2 size-7 -translate-y-1/2"
              aria-label="Clear search"
            >
              <X className="size-3.5" />
            </Button>
          )}
        </div>

        {query.trim() && (
          <p className="text-xs text-muted-foreground">
            {filtered.length} of {segments.length} segments match
            {filtered.length === 0 ? " — try a different term" : ""}
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card p-2">
        {segments.length === 0 ? (
          // Some transcripts have text but no segment timings.
          <p className="whitespace-pre-wrap px-3 py-3 text-sm leading-relaxed text-muted-foreground">
            {transcript.text || "No transcript content."}
          </p>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <Search className="size-5 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No segments match &ldquo;{query}&rdquo;.
            </p>
          </div>
        ) : (
          <div className="max-h-[30rem] space-y-0.5 overflow-y-auto pr-1">
            {filtered.map((segment) => {
              const isActive = segments[activeIndex] === segment;
              return (
                <button
                  key={`${segment.start}-${segment.end}`}
                  type="button"
                  onClick={() => onSeek?.(segment.start)}
                  className={cn(
                    "flex w-full gap-3.5 rounded-xl px-3.5 py-2.5 text-left transition-colors",
                    "hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isActive && "bg-primary/10",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 shrink-0 font-mono text-xs tabular-nums",
                      isActive ? "text-primary" : "text-muted-foreground",
                    )}
                  >
                    {formatTimestamp(segment.start)}
                  </span>
                  <span
                    className={cn(
                      "text-sm leading-relaxed",
                      isActive ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {highlight(segment.text, query).map((part, i) =>
                      part.match ? (
                        <mark
                          key={i}
                          className="rounded bg-warning/30 px-0.5 text-foreground"
                        >
                          {part.text}
                        </mark>
                      ) : (
                        <span key={i}>{part.text}</span>
                      ),
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
