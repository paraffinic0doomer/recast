import { ChevronDown, Video, Dna, Clapperboard, Megaphone, Package } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CampaignStats } from "@/lib/campaign-stats";

interface Step {
  icon: React.ElementType;
  count: number;
  label: string;
  accent: string;
}

/**
 * The funnel: one video expanding into a full campaign. Counts are real —
 * an incomplete pipeline shows the stages it has actually reached.
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
    {
      icon: Video,
      count: hasVideo ? 1 : 0,
      label: hasVideo ? "VIDEO" : "VIDEOS",
      accent: "text-blue-600 dark:text-blue-400 bg-blue-500/10",
    },
    {
      icon: Dna,
      count: hasDna ? 1 : 0,
      label: "CONTENT DNA",
      accent: "text-violet-600 dark:text-violet-400 bg-violet-500/10",
    },
    {
      icon: Clapperboard,
      count: stats.shorts,
      label: stats.shorts === 1 ? "SHORT" : "SHORTS",
      accent: "text-orange-600 dark:text-orange-400 bg-orange-500/10",
    },
    {
      icon: Megaphone,
      count: stats.platforms,
      label: stats.platforms === 1 ? "PLATFORM POST" : "PLATFORM POSTS",
      accent: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10",
    },
    {
      icon: Package,
      count: stats.assets,
      label: stats.assets === 1 ? "CONTENT ASSET" : "CONTENT ASSETS",
      accent: "text-foreground bg-muted",
    },
  ];

  return (
    <div className="flex flex-col items-stretch gap-0 sm:flex-row sm:items-center sm:justify-between">
      {steps.map((step, index) => {
        const Icon = step.icon;
        const reached = step.count > 0;
        return (
          <div key={step.label} className="flex flex-1 flex-col sm:flex-row sm:items-center">
            <div
              className={cn(
                "flex items-center gap-3 rounded-xl border px-4 py-3 sm:flex-col sm:gap-1.5 sm:px-3 sm:py-4 sm:text-center",
                reached ? "bg-card" : "border-dashed opacity-60",
              )}
            >
              <div
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-lg",
                  reached ? step.accent : "bg-muted text-muted-foreground",
                )}
              >
                <Icon className="size-4" />
              </div>
              <div className="min-w-0 sm:space-y-0.5">
                <p className="text-xl font-semibold leading-none tabular-nums text-foreground">
                  {step.count}
                </p>
                <p className="text-[0.6875rem] font-medium uppercase tracking-wider text-muted-foreground">
                  {step.label}
                </p>
              </div>
            </div>

            {index < steps.length - 1 && (
              <ChevronDown
                aria-hidden
                className="mx-auto size-4 shrink-0 text-muted-foreground sm:mx-2 sm:-rotate-90"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
