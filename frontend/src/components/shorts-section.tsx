"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Download,
  Loader2,
  Sparkles,
  Smartphone,
  Quote,
  Captions,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { SectionHeader } from "@/components/workspace";
import { api, ApiError, mediaUrl } from "@/lib/api";
import { toast } from "sonner";
import type { BestMoment, Clip } from "@/types/project";

function formatDuration(seconds: number) {
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface ShortsSectionProps {
  projectId: string;
  moments: BestMoment[];
  initialClips?: Clip[];
}

export function ShortsSection({
  projectId,
  moments,
  initialClips = [],
}: ShortsSectionProps) {
  // Only locally-rendered clips live in state; server clips stay props and are
  // merged at render. Mirroring props into state caused cascading renders.
  const [generated, setGenerated] = useState<Record<string, Clip>>({});
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);
  const [bulkDone, setBulkDone] = useState(0);

  const clips = useMemo(() => {
    const merged: Record<string, Clip> = {};
    for (const clip of initialClips) merged[clip.moment_id] = clip;
    for (const [id, clip] of Object.entries(generated)) merged[id] = clip;
    return merged;
  }, [initialClips, generated]);

  const generate = useCallback(
    async (momentId: string) => {
      setPending((prev) => new Set(prev).add(momentId));
      try {
        const clip = await api.createClip(projectId, momentId);
        setGenerated((prev) => ({ ...prev, [momentId]: clip }));
        return clip;
      } catch (err) {
        toast.error("Couldn't generate short", {
          description:
            err instanceof ApiError ? err.message : "Clip rendering failed",
        });
        return null;
      } finally {
        setPending((prev) => {
          const next = new Set(prev);
          next.delete(momentId);
          return next;
        });
      }
    },
    [projectId],
  );

  const generateAll = useCallback(async () => {
    setBulkRunning(true);
    setBulkDone(0);
    let ok = 0;
    // Sequential: FFmpeg is CPU-bound, so parallel renders would just contend.
    for (const moment of moments) {
      const clip = await generate(moment.id);
      if (clip) ok += 1;
      setBulkDone((n) => n + 1);
    }
    setBulkRunning(false);
    if (ok > 0) {
      toast.success(`${ok} short${ok === 1 ? "" : "s"} ready`, {
        description: "Vertical clips with burned-in captions.",
      });
    }
  }, [moments, generate]);

  const generatedCount = Object.keys(clips).length;

  return (
    <section className="space-y-5">
      <SectionHeader
        title="Shorts"
        count={generatedCount}
        description={
          generatedCount > 0
            ? `${generatedCount} of ${moments.length} rendered — 9:16, captions burned in.`
            : "Vertical clips cut straight from the source video, with captions."
        }
        action={
          <Button onClick={generateAll} disabled={bulkRunning}>
            {bulkRunning ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            {bulkRunning
              ? `Rendering ${bulkDone}/${moments.length}…`
              : "Generate all shorts"}
          </Button>
        }
      />

      {bulkRunning && (
        <Progress
          value={(bulkDone / Math.max(1, moments.length)) * 100}
          className="h-1"
        />
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {moments.map((moment, index) => {
            const clip = clips[moment.id];
            const isPending = pending.has(moment.id);

            return (
              <div
                key={moment.id}
                className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-primary/40"
              >
                {/* 9:16 preview area */}
                <div className="relative aspect-[9/16] w-full bg-surface">
                  {clip ? (
                    <video
                      controls
                      preload="metadata"
                      poster={mediaUrl(clip.thumbnail_url)}
                      src={mediaUrl(clip.video_url)}
                      className="size-full bg-black object-contain"
                    />
                  ) : (
                    <div className="flex size-full flex-col items-center justify-center gap-3 p-4 text-center">
                      {isPending ? (
                        <>
                          <Loader2 className="size-6 animate-spin text-primary" />
                          <p className="text-sm text-muted-foreground">
                            Rendering vertical clip…
                          </p>
                        </>
                      ) : (
                        <>
                          <Smartphone className="size-6 text-muted-foreground" />
                          <p className="text-sm text-muted-foreground">
                            Not generated yet
                          </p>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => generate(moment.id)}
                          >
                            Generate
                          </Button>
                        </>
                      )}
                    </div>
                  )}
                  <span className="absolute left-2.5 top-2.5 rounded-md bg-black/70 px-2 py-0.5 font-mono text-xs tabular-nums text-white">
                    {index + 1}
                  </span>
                </div>

                {/* meta */}
                <div className="flex flex-1 flex-col gap-2.5 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold leading-snug text-foreground">
                      {moment.title}
                    </h3>
                    <span className="shrink-0 font-mono text-sm tabular-nums text-primary">
                      {moment.score}
                    </span>
                  </div>

                  {moment.hook && (
                    <p className="flex gap-1.5 text-xs italic leading-relaxed text-muted-foreground">
                      <Quote className="mt-0.5 size-3 shrink-0" />
                      {moment.hook}
                    </p>
                  )}

                  <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-2">
                    <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-xs tabular-nums text-muted-foreground">
                      {formatDuration(clip?.duration ?? moment.end - moment.start)}
                    </span>
                    {clip?.vertical && (
                      <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">
                        9:16
                      </span>
                    )}
                    {clip?.subtitled && (
                      <span className="flex items-center gap-1 rounded-md bg-success/12 px-2 py-0.5 text-xs font-medium text-success">
                        <Captions className="size-3" />
                        CC
                      </span>
                    )}
                    {clip && (
                      <a
                        href={api.clipDownloadUrl(projectId, clip.clip_id)}
                        className="ml-auto"
                      >
                        <Button size="sm" variant="outline" asChild={false}>
                          <span className="flex items-center gap-1.5">
                            <Download className="size-3.5" />
                            Download
                          </span>
                        </Button>
                      </a>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
      </div>
    </section>
  );
}
