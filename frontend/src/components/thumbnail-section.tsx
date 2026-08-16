"use client";

import { Image as ImageIcon, Loader2, Sparkles, Target, Heart, Copy } from "lucide-react";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { SectionHeader, EmptyState, FieldLabel } from "@/components/workspace";
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
    <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-border bg-surface [container-type:inline-size]">
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
        <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[0.6875rem] text-white">
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
    <section className="space-y-5">
      <SectionHeader
        title="Thumbnail Concepts"
        count={concepts.length}
        description={
          concepts.length > 0
            ? "Three distinct angles, each composed over a real frame from your video."
            : "Three distinct angles built from your Content DNA."
        }
        action={
          <Button onClick={onGenerate} disabled={isGenerating}>
            {isGenerating ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            {isGenerating
              ? "Generating…"
              : concepts.length
                ? "Regenerate"
                : "Generate thumbnails"}
          </Button>
        }
      />

      {!imageGenerationAvailable && concepts.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Previews compose your real video frames with each concept&apos;s
          headline and placement — no image model is configured.
        </p>
      )}

      {concepts.length === 0 ? (
        <EmptyState
          icon={ImageIcon}
          tone="pending"
          title="No thumbnail concepts yet"
          description="Generate three distinct angles built from your Content DNA, each composed over a real frame."
          action={
            <Button size="lg" onClick={onGenerate} disabled={isGenerating}>
              {isGenerating ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {isGenerating ? "Generating…" : "Generate thumbnails"}
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {concepts.map((concept, index) => (
              <div
                key={concept.id || index}
                className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 transition-colors hover:border-primary/40"
              >
                <ThumbnailPreview concept={concept} />

                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <FieldLabel>Headline</FieldLabel>
                    <p className="text-base font-bold leading-snug text-foreground">
                      {concept.headline}
                    </p>
                  </div>
                  <CopyButton value={concept.headline} />
                </div>

                <div className="space-y-3 text-sm">
                  <div>
                    <FieldLabel>Visual concept</FieldLabel>
                    <p className="leading-relaxed text-muted-foreground">
                      {concept.visual_concept}
                    </p>
                  </div>

                  {/* Subject placement is a single keyword, so it reads well as a
                      badge. The emotional angle is a full sentence and must not
                      be one: badges are fixed-height and never wrap. */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Target className="size-3.5 shrink-0 text-muted-foreground" />
                    <FieldLabel>Subject</FieldLabel>
                    <span className="rounded-md bg-secondary px-2 py-0.5 text-xs text-foreground">
                      {concept.subject_placement}
                    </span>
                  </div>

                  {concept.emotional_angle && (
                    <div>
                      <span className="flex items-center gap-1.5">
                        <Heart className="size-3.5 shrink-0 text-muted-foreground" />
                        <FieldLabel>Emotional angle</FieldLabel>
                      </span>
                      <p className="leading-relaxed text-muted-foreground">
                        {concept.emotional_angle}
                      </p>
                    </div>
                  )}

                  {concept.why_it_works && (
                    <div>
                      <FieldLabel>Why it attracts attention</FieldLabel>
                      <p className="leading-relaxed text-muted-foreground">
                        {concept.why_it_works}
                      </p>
                    </div>
                  )}
                </div>

                {concept.recommended_use_case && (
                  <div className="mt-auto rounded-xl bg-surface px-3.5 py-2.5">
                    <FieldLabel>Recommended use</FieldLabel>
                    <p className="text-sm leading-relaxed text-foreground">
                      {concept.recommended_use_case}
                    </p>
                  </div>
                )}
              </div>
          ))}
        </div>
      )}
    </section>
  );
}
