"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Clapperboard,
  Download,
  Loader2,
  Sparkles,
  Smartphone,
  Quote,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
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
        description: "Vertical clips generated with thumbnails.",
      });
    }
  }, [moments, generate]);

  const generatedCount = Object.keys(clips).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Clapperboard className="size-4" />
            Shorts
            {generatedCount > 0 && (
              <span className="text-xs font-normal text-muted-foreground">
                {generatedCount} of {moments.length} generated
              </span>
            )}
          </CardTitle>
          <Button size="sm" onClick={generateAll} disabled={bulkRunning}>
            {bulkRunning ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            {bulkRunning
              ? `Generating ${bulkDone}/${moments.length}…`
              : "Generate All Shorts"}
          </Button>
        </div>
        {bulkRunning && (
          <Progress
            value={(bulkDone / Math.max(1, moments.length)) * 100}
            className="h-1"
          />
        )}
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {moments.map((moment, index) => {
            const clip = clips[moment.id];
            const isPending = pending.has(moment.id);

            return (
              <div
                key={moment.id}
                className="flex flex-col overflow-hidden rounded-xl border bg-card"
              >
                {/* 9:16 preview area */}
                <div className="relative aspect-[9/16] w-full bg-muted">
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
                          <p className="text-xs text-muted-foreground">
                            Rendering vertical clip…
                          </p>
                        </>
                      ) : (
                        <>
                          <Smartphone className="size-6 text-muted-foreground" />
                          <p className="text-xs text-muted-foreground">
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
                  <span className="absolute left-2 top-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                    #{index + 1}
                  </span>
                </div>

                {/* meta */}
                <div className="flex flex-1 flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold leading-snug text-foreground">
                      {moment.title}
                    </h3>
                    <span className="shrink-0 text-sm font-semibold tabular-nums text-foreground">
                      {moment.score}
                      <span className="text-xs font-normal text-muted-foreground">
                        /100
                      </span>
                    </span>
                  </div>

                  {moment.hook && (
                    <p className="flex gap-1.5 text-xs italic leading-relaxed text-muted-foreground">
                      <Quote className="mt-0.5 size-3 shrink-0" />
                      {moment.hook}
                    </p>
                  )}

                  <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
                    <Badge variant="secondary" className="font-normal">
                      {formatDuration(clip?.duration ?? moment.end - moment.start)}
                    </Badge>
                    {clip?.vertical && (
                      <Badge variant="outline" className="font-normal">
                        9:16
                      </Badge>
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
      </CardContent>
    </Card>
  );
}
