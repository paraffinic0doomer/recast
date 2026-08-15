"use client";

import { Image as ImageIcon, Loader2, Sparkles, Target, Heart, Copy } from "lucide-react";
import { useCallback, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import type { ThumbnailConcept } from "@/types/project";

const TEXT_POSITION_CLASSES: Record<string, string> = {
  left: "items-center justify-start text-left",
  right: "items-center justify-end text-right",
  center: "items-center justify-center text-center",
  top: "items-start justify-center text-center",
  bottom: "items-end justify-center text-center",
};

/** Darken the side opposite the text so the headline stays readable. */
const SCRIM_CLASSES: Record<string, string> = {
  left: "bg-gradient-to-r from-black/85 via-black/40 to-transparent",
  right: "bg-gradient-to-l from-black/85 via-black/40 to-transparent",
  center: "bg-black/55",
  top: "bg-gradient-to-b from-black/85 to-transparent",
  bottom: "bg-gradient-to-t from-black/85 to-transparent",
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy");
    }
  }, [value]);
  return (
    <Button size="sm" variant="ghost" onClick={copy}>
      <Copy className="size-3.5" />
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

/** Composes the concept over a real extracted frame, per its spec. */
function ThumbnailPreview({ concept }: { concept: ThumbnailConcept }) {
  const position = concept.text_position || "left";

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-lg border bg-muted [container-type:inline-size]">
      {concept.frame_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={mediaUrl(concept.frame_url)}
          alt={concept.visual_concept || "Thumbnail frame"}
          className="size-full object-cover"
        />
      ) : (
        <div className="flex size-full items-center justify-center bg-muted">
          <ImageIcon className="size-6 text-muted-foreground" />
        </div>
      )}

      <div className={cn("absolute inset-0", SCRIM_CLASSES[position] ?? SCRIM_CLASSES.left)} />

      <div
        className={cn(
          "absolute inset-0 flex p-4",
          TEXT_POSITION_CLASSES[position] ?? TEXT_POSITION_CLASSES.left,
        )}
      >
        <p
          className={cn(
            "font-black uppercase leading-[1.05] tracking-tight",
            "drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]",
            // Long words must wrap rather than run off the frame, and the size
            // scales with the card so headlines stay inside at any grid width.
            "max-w-full break-words hyphens-auto",
            "text-[clamp(0.9rem,4.2cqw,1.6rem)]",
          )}
          style={{ color: concept.accent_color }}
        >
          {concept.headline}
        </p>
      </div>

      {concept.timestamp != null && (
        <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-white">
          frame @ {Math.floor(concept.timestamp / 60)}:
          {String(Math.floor(concept.timestamp % 60)).padStart(2, "0")}
        </span>
      )}
    </div>
  );
}

interface ThumbnailSectionProps {
  concepts: ThumbnailConcept[];
  isGenerating: boolean;
  imageGenerationAvailable?: boolean;
  onGenerate: () => void;
}

export function ThumbnailSection({
  concepts,
  isGenerating,
  imageGenerationAvailable = false,
  onGenerate,
}: ThumbnailSectionProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ImageIcon className="size-4" />
            Thumbnail Concepts
            {concepts.length > 0 && (
              <span className="text-xs font-normal text-muted-foreground">
                {concepts.length} alternatives
              </span>
            )}
          </CardTitle>
          <Button size="sm" onClick={onGenerate} disabled={isGenerating}>
            {isGenerating ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            {isGenerating
              ? "Generating…"
              : concepts.length
                ? "Regenerate"
                : "Generate Thumbnails"}
          </Button>
        </div>
        {!imageGenerationAvailable && concepts.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Previews compose your real video frames with each concept&apos;s
            headline and placement — no image model is configured.
          </p>
        )}
      </CardHeader>

      <CardContent>
        {concepts.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed py-12 text-center">
            <ImageIcon className="size-6 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">
                No thumbnail concepts yet
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Generate three distinct angles built from your Content DNA.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {concepts.map((concept, index) => (
              <div
                key={concept.id || index}
                className="flex flex-col gap-3 rounded-xl border bg-card p-4"
              >
                <ThumbnailPreview concept={concept} />

                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Headline
                    </span>
                    <p className="text-sm font-semibold leading-snug text-foreground">
                      {concept.headline}
                    </p>
                  </div>
                  <CopyButton value={concept.headline} />
                </div>

                <div className="space-y-2.5 text-sm">
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Visual concept
                    </span>
                    <p className="leading-relaxed text-muted-foreground">
                      {concept.visual_concept}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline" className="gap-1 font-normal">
                      <Target className="size-3" />
                      Subject: {concept.subject_placement}
                    </Badge>
                    <Badge variant="outline" className="gap-1 font-normal">
                      <Heart className="size-3" />
                      {concept.emotional_angle}
                    </Badge>
                  </div>

                  {concept.why_it_works && (
                    <div>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Why it attracts attention
                      </span>
                      <p className="leading-relaxed text-muted-foreground">
                        {concept.why_it_works}
                      </p>
                    </div>
                  )}
                </div>

                {concept.recommended_use_case && (
                  <div className="mt-auto rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Recommended use
                    </span>
                    <p className="text-xs leading-relaxed text-foreground">
                      {concept.recommended_use_case}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
