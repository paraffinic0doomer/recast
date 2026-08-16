"use client";

import { Sparkles, Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

const PLATFORM_NAMES = [
  "YouTube",
  "Instagram",
  "TikTok",
  "Facebook",
  "LinkedIn",
  "X",
];

/**
 * The primary action of the whole product. Shown once the AI understands the
 * video and before a campaign exists, so the next step is never ambiguous.
 */
export function GenerateCampaignCta({
  isGenerating,
  onGenerate,
}: {
  isGenerating: boolean;
  onGenerate: () => void;
  platformCount?: number;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/30 bg-primary/[0.05] p-6 sm:p-7">
      {isGenerating && <span className="absolute inset-0 ai-shimmer" />}

      <div className="relative flex flex-wrap items-center justify-between gap-x-8 gap-y-5">
        <div className="flex min-w-[18rem] flex-1 items-start gap-4">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/25">
            <Sparkles className="size-5" />
          </span>
          <div className="min-w-0 space-y-2">
            <h3 className="text-lg font-semibold tracking-tight text-foreground">
              Turn this into a full campaign
            </h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              RECAST writes a native post for every platform from what it learned
              about your video — a different tone, length and hook for each.
            </p>
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {PLATFORM_NAMES.map((name) => (
                <span
                  key={name}
                  className="rounded-md bg-secondary px-2 py-0.5 text-xs text-muted-foreground"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>

        <Button size="lg" onClick={onGenerate} disabled={isGenerating}>
          {isGenerating ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Generating campaign…
            </>
          ) : (
            <>
              Generate campaign
              <ArrowRight className="size-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
