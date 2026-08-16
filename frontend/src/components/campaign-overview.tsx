import { ChevronRight, Video, Dna, Clapperboard, Megaphone, Package } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CampaignStats } from "@/lib/campaign-stats";

interface Step {
  icon: React.ElementType;
  count: number;
  label: string;
}

/**
 * The funnel: one video expanding into a full campaign. Counts are real — an
 * incomplete pipeline shows only the stages it has actually reached, and the
 * final tile is emphasised because it is the number that tells the story.
 */
export function CampaignOverview({
  stats,
  hasVideo,
  hasDna,
}: {
  stats: CampaignStats;
  hasVideo: boolean;
  hasDna: boolean;
}) {
  const steps: Step[] = [
    { icon: Video, count: hasVideo ? 1 : 0, label: hasVideo ? "Video" : "Videos" },
    { icon: Dna, count: hasDna ? 1 : 0, label: "Content DNA" },
    {
      icon: Clapperboard,
      count: stats.shorts,
      label: stats.shorts === 1 ? "Short" : "Shorts",
    },
    {
      icon: Megaphone,
      count: stats.platforms,
      label: stats.platforms === 1 ? "Platform post" : "Platform posts",
    },
    {
      icon: Package,
      count: stats.assets,
      label: stats.assets === 1 ? "Content asset" : "Content assets",
    },
  ];

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
      {steps.map((step, index) => {
        const Icon = step.icon;
        const reached = step.count > 0;
        const isFinal = index === steps.length - 1;

        return (
          <div
            key={step.label}
            className="flex flex-1 items-center gap-2"
          >
            <div
              className={cn(
                "flex w-full flex-1 items-center gap-3 rounded-xl border px-4 py-3 sm:flex-col sm:items-start sm:gap-2.5",
                reached
                  ? isFinal
                    ? "border-primary/40 bg-primary/[0.06]"
                    : "border-border bg-card"
                  : "border-dashed border-border bg-transparent opacity-50",
              )}
            >
              <span
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-lg",
                  reached && isFinal
                    ? "bg-primary text-primary-foreground"
                    : reached
                      ? "bg-secondary text-muted-foreground"
                      : "bg-secondary/60 text-muted-foreground",
                )}
              >
                <Icon className="size-3.5" />
              </span>
              <div className="min-w-0">
                <p
                  className={cn(
                    "text-2xl font-semibold leading-tight tabular-nums tracking-tight",
                    reached && isFinal ? "text-primary" : "text-foreground",
                  )}
                >
                  {step.count}
                </p>
                <p className="mt-1.5 text-xs text-muted-foreground">{step.label}</p>
              </div>
            </div>

            {index < steps.length - 1 && (
              <ChevronRight
                aria-hidden
                className="hidden size-4 shrink-0 self-center text-muted-foreground/50 sm:block"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
