"use client";

import { useMemo, useState } from "react";
import { Search, FileText, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

  const segments = transcript.segments ?? [];

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
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="size-4" />
            Transcript
          </CardTitle>
          <div className="flex items-center gap-2">
            {transcript.language && (
              <Badge variant="secondary" className="uppercase">
                {transcript.language}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {segments.length} segment{segments.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>

        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search transcript…"
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
      </CardHeader>

      <CardContent>
        {segments.length === 0 ? (
          // Some transcripts have text but no segment timings.
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
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
          <div className="max-h-[26rem] space-y-1 overflow-y-auto pr-1">
            {filtered.map((segment) => {
              const isActive = segments[activeIndex] === segment;
              return (
                <button
                  key={`${segment.start}-${segment.end}`}
                  type="button"
                  onClick={() => onSeek?.(segment.start)}
                  className={cn(
                    "flex w-full gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                    "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
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
                          className="rounded bg-amber-200 px-0.5 text-foreground dark:bg-amber-500/40"
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
      </CardContent>
    </Card>
  );
}
