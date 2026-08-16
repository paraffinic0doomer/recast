"use client";

import { Flame, Play, Scissors, Loader2, Quote, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SectionHeader, FieldLabel } from "@/components/workspace";
import { ScoreRing } from "@/components/score-ring";
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

/** The three signals a creator actually decides on, in plain language. */
const SCORE_LABELS: { key: keyof BestMoment["scores"]; label: string }[] = [
  { key: "hook_strength", label: "Hook" },
  { key: "information_value", label: "Information" },
  { key: "emotional_interest", label: "Emotion" },
  { key: "standalone_quality", label: "Standalone" },
];

function barTone(score: number) {
  if (score >= 85) return "bg-success";
  if (score >= 70) return "bg-primary";
  if (score >= 50) return "bg-warning";
  return "bg-muted-foreground/40";
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="font-mono text-xs tabular-nums text-foreground">
          {value}
        </span>
      </div>
      <div
        className="h-1 w-full overflow-hidden rounded-full bg-secondary"
        role="meter"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={cn("h-full rounded-full transition-all duration-500", barTone(value))}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

interface BestMomentsPanelProps {
  moments: BestMoment[];
  onSeek?: (seconds: number) => void;
  /** Which moments already have a rendered short, keyed by moment id. */
  generatedMomentIds?: Set<string>;
  generatingMomentId?: string | null;
  onGenerateShort?: (momentId: string) => void;
}

/**
 * Ranked clip recommendations. Reads like a premium video tool's suggestion
 * feed: rank, title, timecode, an overall ring, and the score breakdown that
 * justifies it — so the ranking is explainable rather than asserted.
 */
export function BestMomentsPanel({
  moments,
  onSeek,
  generatedMomentIds,
  generatingMomentId,
  onGenerateShort,
}: BestMomentsPanelProps) {
  const longVideo = moments.some((m) => m.end >= 3600);

  return (
    <section className="space-y-5">
      <SectionHeader
        title="Best Moments"
        count={moments.length}
        description="Ranked by how well each segment would stand on its own as a short."
      />

      <div className="space-y-4">
        {moments.map((moment, index) => {
          const hasClip = generatedMomentIds?.has(moment.id) ?? false;
          const isGenerating = generatingMomentId === moment.id;
          const isTop = index === 0;

          return (
            <article
              key={`${moment.start}-${moment.end}`}
              className={cn(
                "rounded-2xl border bg-card p-6 transition-colors",
                isTop ? "border-primary/40" : "border-border hover:border-border/80",
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
                <div className="flex min-w-[14rem] flex-1 items-start gap-4">
                  <span
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-xl font-mono text-sm tabular-nums",
                      isTop
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary text-muted-foreground",
                    )}
                  >
                    {index + 1}
                  </span>

                  <div className="min-w-0 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-[1.05rem] font-semibold leading-snug text-foreground">
                        {moment.title}
                      </h3>
                      {isTop && (
                        <span className="flex items-center gap-1 rounded-md bg-primary/12 px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-wider text-primary">
                          <Flame className="size-3" />
                          Top pick
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-xs tabular-nums text-muted-foreground">
                      {formatTimecode(moment.start, longVideo)} –{" "}
                      {formatTimecode(moment.end, longVideo)}
                      <span className="ml-2 font-sans">
                        {Math.round(moment.end - moment.start)}s
                      </span>
                    </p>
                  </div>
                </div>

                <ScoreRing value={moment.score} size={64} label="Viral score" />
              </div>

              {moment.hook && (
                <blockquote className="mt-5 flex gap-3 rounded-xl border-l-2 border-primary bg-surface px-4 py-3">
                  <Quote className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  <p className="text-sm italic leading-relaxed text-foreground">
                    {moment.hook}
                  </p>
                </blockquote>
              )}

              <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3.5 sm:grid-cols-4">
                {SCORE_LABELS.map(({ key, label }) => (
                  <ScoreBar key={key} label={label} value={moment.scores[key]} />
                ))}
              </div>

              {moment.reason && (
                <div className="mt-5">
                  <FieldLabel>Why this works</FieldLabel>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {moment.reason}
                  </p>
                </div>
              )}

              <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-border pt-5">
                {onGenerateShort && (
                  <Button
                    size="lg"
                    onClick={() => onGenerateShort(moment.id)}
                    disabled={isGenerating}
                  >
                    {isGenerating ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Scissors className="size-4" />
                    )}
                    {isGenerating
                      ? "Rendering…"
                      : hasClip
                        ? "Regenerate short"
                        : "Generate short"}
                  </Button>
                )}
                <Button size="lg" variant="outline" onClick={() => onSeek?.(moment.start)}>
                  <Play className="size-4" />
                  Preview in video
                </Button>
                {hasClip && (
                  <span className="flex items-center gap-1.5 rounded-lg bg-success/12 px-2.5 py-1 text-xs font-medium text-success">
                    <Check className="size-3.5" />
                    Short ready
                  </span>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
