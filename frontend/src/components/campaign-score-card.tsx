"use client";

import {
  Gauge,
  Loader2,
  RotateCw,
  Lightbulb,
  ArrowUpRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { CampaignEvaluation } from "@/types/project";

const DIMENSIONS: { key: keyof CampaignEvaluation; label: string }[] = [
  { key: "content_quality", label: "Content quality" },
  { key: "platform_adaptation", label: "Platform adaptation" },
  { key: "hook_strength", label: "Hook strength" },
  { key: "source_consistency", label: "Source consistency" },
  { key: "seo", label: "SEO quality" },
  { key: "cta", label: "CTA quality" },
];

function tone(score: number) {
  // Stroke colours are literal hex, not derived class names: Tailwind only
  // generates classes it can see in the source, so a runtime-built
  // "stroke-amber-500" would silently render no colour at all.
  if (score >= 85)
    return {
      bar: "bg-emerald-500",
      text: "text-emerald-600 dark:text-emerald-400",
      stroke: "#10B981",
    };
  if (score >= 70)
    return {
      bar: "bg-amber-500",
      text: "text-amber-600 dark:text-amber-400",
      stroke: "#F59E0B",
    };
  return {
    bar: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
    stroke: "#EF4444",
  };
}

function verdict(score: number) {
  if (score >= 90) return "Excellent";
  if (score >= 80) return "Strong";
  if (score >= 70) return "Solid";
  if (score >= 55) return "Needs work";
  return "Weak";
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-red-500/10 text-red-600 dark:text-red-400 border-transparent",
  medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-transparent",
  low: "bg-muted text-muted-foreground border-transparent",
};

/** Circular gauge for the headline score. */
function ScoreDial({ score }: { score: number }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);
  const t = tone(score);

  return (
    <div className="relative size-32 shrink-0">
      <svg viewBox="0 0 120 120" className="size-full -rotate-90">
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="9"
          className="stroke-muted"
        />
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          stroke={t.stroke}
          className="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold leading-none tabular-nums text-foreground">
          {score}
        </span>
        <span className="text-sm text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}

function DimensionBar({ label, value }: { label: string; value: number }) {
  const t = tone(value);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-medium tabular-nums", t.text)}>{value}</span>
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
          className={cn("h-full rounded-full transition-all duration-700", t.bar)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

interface CampaignScoreCardProps {
  evaluation: CampaignEvaluation | null;
  completenessScore: number | null;
  isEvaluating: boolean;
  onEvaluate: () => void;
  hasCampaign: boolean;
}

export function CampaignScoreCard({
  evaluation,
  completenessScore,
  isEvaluating,
  onEvaluate,
  hasCampaign,
}: CampaignScoreCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <Gauge className="size-4" />
            Campaign Score
          </CardTitle>
          {hasCampaign && (
            <Button
              size="sm"
              variant="outline"
              onClick={onEvaluate}
              disabled={isEvaluating}
            >
              {isEvaluating ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RotateCw className="size-3.5" />
              )}
              {isEvaluating ? "Scoring…" : evaluation ? "Re-score" : "Score campaign"}
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent>
        {!evaluation ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center">
            <Gauge className="size-5 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">
              {hasCampaign ? "Campaign not scored yet" : "No campaign to score"}
            </p>
            <p className="max-w-md text-sm text-muted-foreground">
              {hasCampaign
                ? "Run the evaluator to grade quality, platform adaptation and CTA strength."
                : "Generate a campaign first, then it can be evaluated."}
            </p>
            {completenessScore != null && (
              <p className="mt-1 text-sm text-muted-foreground">
                Completeness score: {completenessScore}/100
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-8">
            {/* headline */}
            <div className="flex flex-wrap items-center gap-6">
              <ScoreDial score={evaluation.overall} />
              <div className="min-w-[12rem] flex-1 space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Overall
                </p>
                <p className={cn("text-lg font-semibold", tone(evaluation.overall).text)}>
                  {verdict(evaluation.overall)}
                </p>
                {evaluation.summary && (
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {evaluation.summary}
                  </p>
                )}
                {completenessScore != null && (
                  <p className="pt-1 text-xs text-muted-foreground">
                    Completeness {completenessScore}/100 · quality scored separately
                  </p>
                )}
              </div>
            </div>

            <Separator />

            {/* dimensions */}
            <div className="grid grid-cols-1 gap-x-10 gap-y-5 sm:grid-cols-2">
              {DIMENSIONS.map(({ key, label }) => (
                <DimensionBar
                  key={key}
                  label={label}
                  value={evaluation[key] as number}
                />
              ))}
            </div>

            {/* improvements */}
            {evaluation.improvements.length > 0 && (
              <>
                <Separator />
                <div className="space-y-3">
                  <h4 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                    <Lightbulb className="size-4" />
                    {evaluation.improvements.length} improvement
                    {evaluation.improvements.length === 1 ? "" : "s"} that could make
                    this campaign stronger
                  </h4>
                  <ul className="space-y-2">
                    {evaluation.improvements.map((item, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-3 rounded-lg border bg-muted/30 px-4 py-3"
                      >
                        <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {item.area && (
                              <span className="text-xs font-semibold text-foreground">
                                {item.area}
                              </span>
                            )}
                            <Badge
                              className={cn(
                                "text-[0.6875rem] font-medium uppercase",
                                PRIORITY_STYLES[item.priority] ?? PRIORITY_STYLES.medium,
                              )}
                            >
                              {item.priority}
                            </Badge>
                          </div>
                          <p className="text-sm leading-relaxed text-muted-foreground">
                            {item.suggestion}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
