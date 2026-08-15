"use client";

import { Sparkles, Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * The primary action of the whole product. Shown once the AI understands the
 * video and before a campaign exists, so the next step is never ambiguous.
 */
export function GenerateCampaignCta({
  isGenerating,
  onGenerate,
  platformCount = 6,
}: {
  isGenerating: boolean;
  onGenerate: () => void;
  platformCount?: number;
}) {
  return (
    <div className="rounded-xl border-2 border-primary/30 bg-gradient-to-br from-primary/5 to-transparent p-6">
      <div className="flex flex-wrap items-center justify-between gap-5">
        <div className="flex min-w-[16rem] flex-1 items-start gap-4">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles className="size-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground">
              Turn this into a full campaign
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              RECAST will write native posts for all {platformCount} platforms
              from what it learned about your video — different tone, length and
              hook for each.
            </p>
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
              Generate Campaign
              <ArrowRight className="size-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
