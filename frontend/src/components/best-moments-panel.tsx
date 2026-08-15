"use client";

import { Flame, Play, Scissors, Loader2, Quote } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { BestMoment } from "@/types/project";

/** 00:03:14 for long videos, 03:14 for short ones. */
function formatTimecode(seconds: number, forceHours = false): string {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 || forceHours ? `${String(h).padStart(2, "0")}:${mm}:${ss}` : `${mm}:${ss}`;
}

const SCORE_LABELS: { key: keyof BestMoment["scores"]; label: string }[] = [
  { key: "hook_strength", label: "Hook strength" },
  { key: "standalone_quality", label: "Standalone" },
  { key: "information_value", label: "Information" },
  { key: "emotional_interest", label: "Emotional pull" },
];

function scoreTone(score: number) {
  if (score >= 85) return "bg-emerald-500";
  if (score >= 70) return "bg-amber-500";
  return "bg-muted-foreground/40";
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums text-foreground">{value}</span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={cn("h-full rounded-full transition-all", scoreTone(value))}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

const RANK_STYLES = [
  "bg-orange-500 text-white",
  "bg-orange-500/80 text-white",
  "bg-orange-500/60 text-white",
  "bg-muted text-muted-foreground",
  "bg-muted text-muted-foreground",
];

interface BestMomentsPanelProps {
  moments: BestMoment[];
  onSeek?: (seconds: number) => void;
  /** Which moments already have a rendered short, keyed by moment id. */
  generatedMomentIds?: Set<string>;
  generatingMomentId?: string | null;
  onGenerateShort?: (momentId: string) => void;
}

export function BestMomentsPanel({
  moments,
  onSeek,
  generatedMomentIds,
  generatingMomentId,
  onGenerateShort,
}: BestMomentsPanelProps) {
  const longVideo = moments.some((m) => m.end >= 3600);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Flame className="size-4" />
            Best Moments
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            {moments.length} clip-worthy {moments.length === 1 ? "moment" : "moments"}
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {moments.map((moment, index) => {
          const hasClip = generatedMomentIds?.has(moment.id) ?? false;
          const isGenerating = generatingMomentId === moment.id;
          return (
            <div
              key={`${moment.start}-${moment.end}`}
              className="rounded-xl border bg-card p-5"
            >
              {/* header: rank, title, timecode, score */}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span
                    className={cn(
                      "flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold",
                      RANK_STYLES[index] ?? RANK_STYLES[4],
                    )}
                  >
                    {index < 3 && <Flame className="size-3" />}#{index + 1}
                  </span>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold leading-snug text-foreground">
                      {moment.title}
                    </h3>
                    <p className="mt-0.5 font-mono text-xs tabular-nums text-muted-foreground">
                      {formatTimecode(moment.start, longVideo)} —{" "}
                      {formatTimecode(moment.end, longVideo)}
                      <span className="ml-2 font-sans">
                        ({Math.round(moment.end - moment.start)}s)
                      </span>
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-2xl font-semibold leading-none tabular-nums text-foreground">
                    {moment.score}
                    <span className="text-sm font-normal text-muted-foreground">
                      /100
                    </span>
                  </div>
                </div>
              </div>

              {/* hook */}
              {moment.hook && (
                <div className="mt-4 flex gap-2 rounded-lg bg-muted/50 px-3 py-2">
                  <Quote className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  <p className="text-sm italic leading-relaxed text-foreground">
                    {moment.hook}
                  </p>
                </div>
              )}

              {/* score breakdown */}
              <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                {SCORE_LABELS.map(({ key, label }) => (
                  <ScoreBar key={key} label={label} value={moment.scores[key]} />
                ))}
              </div>

              {/* reason */}
              {moment.reason && (
                <div className="mt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Why this works
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {moment.reason}
                  </p>
                </div>
              )}

              <Separator className="my-4" />

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onSeek?.(moment.start)}
                >
                  <Play className="size-3.5" />
                  Play in video
                </Button>
                {onGenerateShort && (
                  <Button
                    size="sm"
                    onClick={() => onGenerateShort(moment.id)}
                    disabled={isGenerating}
                  >
                    {isGenerating ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Scissors className="size-3.5" />
                    )}
                    {isGenerating
                      ? "Generating…"
                      : hasClip
                        ? "Regenerate Short"
                        : "Generate Short"}
                  </Button>
                )}
                {hasClip && (
                  <Badge variant="secondary" className="font-normal">
                    Short ready
                  </Badge>
                )}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
