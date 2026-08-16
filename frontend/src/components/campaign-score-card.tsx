"use client";

import {
  Gauge,
  Loader2,
  RotateCw,
  Lightbulb,
  ArrowUpRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SectionHeader, EmptyState, FieldLabel } from "@/components/workspace";
import { AiEngineNotice } from "@/components/ai-engine-notice";
import { ScoreRing } from "@/components/score-ring";
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
  // Literal class names per band: Tailwind only generates classes it can see in
  // the source, so a runtime-built "bg-" + colour would render nothing at all.
  if (score >= 85) return { bar: "bg-success", text: "text-success" };
  if (score >= 70) return { bar: "bg-primary", text: "text-primary" };
  if (score >= 50) return { bar: "bg-warning", text: "text-warning" };
  return { bar: "bg-destructive", text: "text-destructive" };
}

function verdict(score: number) {
  if (score >= 90) return "Excellent";
  if (score >= 80) return "Strong";
  if (score >= 70) return "Solid";
  if (score >= 55) return "Needs work";
  return "Weak";
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-destructive/12 text-destructive",
  medium: "bg-warning/12 text-warning",
  low: "bg-secondary text-muted-foreground",
};

function DimensionBar({ label, value }: { label: string; value: number }) {
  const t = tone(value);
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-mono tabular-nums", t.text)}>{value}</span>
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
    <section className="space-y-5">
      <SectionHeader
        title="Campaign Score"
        description="An independent pass that grades the campaign and says what would make it stronger."
        action={
          hasCampaign ? (
            <Button variant="outline" onClick={onEvaluate} disabled={isEvaluating}>
              {isEvaluating ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RotateCw className="size-4" />
              )}
              {isEvaluating ? "Scoring…" : evaluation ? "Re-score" : "Score campaign"}
            </Button>
          ) : undefined
        }
      />

      <AiEngineNotice />

      {!evaluation ? (
        <EmptyState
          icon={Gauge}
          tone={hasCampaign ? "pending" : "default"}
          title={hasCampaign ? "Campaign not scored yet" : "No campaign to score"}
          description={
            hasCampaign
              ? "Grade quality, platform adaptation, hooks, SEO and CTA strength — and get concrete suggestions."
              : "Generate a campaign first, then it can be evaluated."
          }
          action={
            hasCampaign ? (
              <Button size="lg" onClick={onEvaluate} disabled={isEvaluating}>
                {isEvaluating ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Gauge className="size-4" />
                )}
                {isEvaluating ? "Scoring…" : "Score campaign"}
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-8">
            {/* headline */}
            <div className="flex flex-wrap items-center gap-8 rounded-2xl border border-border bg-card px-6 py-6">
              <ScoreRing value={evaluation.overall} size={112} />
              <div className="min-w-[12rem] flex-1 space-y-2">
                <FieldLabel>Overall</FieldLabel>
                <p className={cn("text-2xl font-semibold tracking-tight", tone(evaluation.overall).text)}>
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

            {/* dimensions */}
            <div className="rounded-2xl border border-border bg-card px-6 py-6">
              <div className="grid grid-cols-1 gap-x-10 gap-y-5 sm:grid-cols-2">
                {DIMENSIONS.map(({ key, label }) => (
                  <DimensionBar
                    key={key}
                    label={label}
                    value={evaluation[key] as number}
                  />
                ))}
              </div>
            </div>

            {/* improvements */}
            {evaluation.improvements.length > 0 && (
              <>
                <div className="space-y-3">
                  <h4 className="flex items-center gap-2 text-[0.95rem] font-semibold text-foreground">
                    <Lightbulb className="size-4 text-warning" />
                    {evaluation.improvements.length} improvement
                    {evaluation.improvements.length === 1 ? "" : "s"} that could make
                    this campaign stronger
                  </h4>
                  <ul className="space-y-2">
                    {evaluation.improvements.map((item, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-3 rounded-xl border border-border bg-surface px-4 py-3.5"
                      >
                        <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {item.area && (
                              <span className="text-sm font-semibold text-foreground">
                                {item.area}
                              </span>
                            )}
                            <span
                              className={cn(
                                "rounded-md px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-wider",
                                PRIORITY_STYLES[item.priority] ?? PRIORITY_STYLES.medium,
                              )}
                            >
                              {item.priority}
                            </span>
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
    </section>
  );
}
