"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { WifiOff, Library, Clapperboard, Image as ImageIcon, Download } from "lucide-react";
import { Page, PageHeader, EmptyState, SectionHeader } from "@/components/workspace";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useProjects } from "@/lib/use-projects";
import { api, mediaUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Clip, ThumbnailConcept } from "@/types/project";

interface OwnedClip extends Clip {
  projectId: string;
  projectTitle: string;
}

interface OwnedConcept extends ThumbnailConcept {
  projectId: string;
  projectTitle: string;
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function AssetsPage() {
  const { projects, error } = useProjects();
  // null until the fan-out settles, which is what distinguishes "still
  // loading" from "loaded, and there genuinely is nothing here".
  const [assets, setAssets] = useState<{
    clips: OwnedClip[];
    concepts: OwnedConcept[];
  } | null>(null);

  // Fan out only over projects that actually produced something; these are
  // plain database reads, so no generation is triggered by browsing.
  useEffect(() => {
    if (!projects) return;
    let cancelled = false;

    const candidates = projects.filter(
      (p) => p.clip_count > 0 || p.has_content_dna,
    );

    Promise.all(
      candidates.map(async (project) => {
        const [clipRes, thumbRes] = await Promise.all([
          project.clip_count > 0
            ? api.getClips(project.id).catch(() => null)
            : Promise.resolve(null),
          api.getThumbnails(project.id).catch(() => null),
        ]);
        return {
          clips: (clipRes?.clips ?? []).map((c) => ({
            ...c,
            projectId: project.id,
            projectTitle: project.title,
          })),
          concepts: (thumbRes?.concepts ?? []).map((c) => ({
            ...c,
            projectId: project.id,
            projectTitle: project.title,
          })),
        };
      }),
    ).then((results) => {
      if (cancelled) return;
      setAssets({
        clips: results.flatMap((r) => r.clips),
        concepts: results.flatMap((r) => r.concepts),
      });
    });

    return () => {
      cancelled = true;
    };
  }, [projects]);

  const busy = projects === null || assets === null;
  const clips = assets?.clips ?? [];
  const concepts = assets?.concepts ?? [];
  const total = clips.length + concepts.length;

  return (
    <Page className="space-y-8">
      <PageHeader
        eyebrow="Workspace"
        title="Assets"
        description="Every file RECAST has rendered for you — vertical shorts with burned-in captions, and thumbnail concepts composed over real frames."
      />

      {error && (
        <Alert variant="destructive">
          <WifiOff className="size-4" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {busy && !error && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[9/16] rounded-2xl" />
          ))}
        </div>
      )}

      {!busy && total === 0 && (
        <EmptyState
          icon={Library}
          title="No assets yet"
          description="Generate a short or a set of thumbnail concepts from any project and the rendered files will collect here."
          action={
            <Button asChild>
              <Link href="/projects">Browse projects</Link>
            </Button>
          }
        />
      )}

      {!busy && total > 0 && (
        <Tabs defaultValue="shorts">
          <TabsList>
            <TabsTrigger value="shorts" className="gap-1.5">
              <Clapperboard className="size-3.5" />
              Shorts
              {clips.length > 0 && (
                <span className="font-mono text-xs tabular-nums opacity-70">
                  {clips.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="thumbnails" className="gap-1.5">
              <ImageIcon className="size-3.5" />
              Thumbnails
              {concepts.length > 0 && (
                <span className="font-mono text-xs tabular-nums opacity-70">
                  {concepts.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="shorts" className="mt-6 space-y-5">
            {clips.length === 0 ? (
              <EmptyState
                icon={Clapperboard}
                title="No shorts rendered yet"
                description="Open a project's Shorts tab and generate a clip from one of its best moments."
              />
            ) : (
              <>
                <SectionHeader
                  title="Vertical shorts"
                  count={clips.length}
                  description="1080×1920, captions burned in, ready to upload."
                />
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                  {clips.map((clip) => (
                    <div
                      key={`${clip.projectId}-${clip.clip_id}`}
                      className="overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-primary/40"
                    >
                      <video
                        controls
                        preload="metadata"
                        poster={mediaUrl(clip.thumbnail_url)}
                        src={mediaUrl(clip.video_url)}
                        className="aspect-[9/16] w-full bg-black object-cover"
                      />
                      <div className="space-y-2 p-3.5">
                        <p className="line-clamp-2 text-sm font-medium leading-snug text-foreground">
                          {clip.title}
                        </p>
                        <Link
                          href={`/projects/${clip.projectId}`}
                          className="line-clamp-1 block text-xs text-muted-foreground hover:text-primary"
                        >
                          {clip.projectTitle}
                        </Link>
                        <div className="flex items-center justify-between gap-2 pt-0.5">
                          <span className="font-mono text-xs tabular-nums text-muted-foreground">
                            {formatDuration(clip.duration)}
                          </span>
                          <Button size="xs" variant="ghost" asChild>
                            <a
                              href={api.clipDownloadUrl(clip.projectId, clip.clip_id)}
                            >
                              <Download className="size-3" />
                              Save
                            </a>
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </TabsContent>

          <TabsContent value="thumbnails" className="mt-6 space-y-5">
            {concepts.length === 0 ? (
              <EmptyState
                icon={ImageIcon}
                title="No thumbnail concepts yet"
                description="Open a project's Thumbnails tab to generate three distinct angles from its Content DNA."
              />
            ) : (
              <>
                <SectionHeader
                  title="Thumbnail concepts"
                  count={concepts.length}
                  description="Each headline composed over a real frame from the source video."
                />
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {concepts.map((concept, i) => (
                    <div
                      key={`${concept.projectId}-${concept.id || i}`}
                      className="overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-primary/40"
                    >
                      <div className="relative aspect-video w-full overflow-hidden bg-secondary">
                        {concept.frame_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={mediaUrl(concept.frame_url)}
                            alt={concept.visual_concept || concept.headline}
                            className="size-full object-cover"
                          />
                        ) : (
                          <div className="flex size-full items-center justify-center">
                            <ImageIcon className="size-6 text-muted-foreground" />
                          </div>
                        )}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/25 to-transparent" />
                        <p
                          className={cn(
                            "absolute inset-x-0 bottom-0 p-4 text-lg font-bold uppercase leading-tight tracking-tight",
                            "drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]",
                          )}
                          style={{ color: concept.accent_color }}
                        >
                          {concept.headline}
                        </p>
                      </div>
                      <div className="p-3.5">
                        <Link
                          href={`/projects/${concept.projectId}`}
                          className="line-clamp-1 block text-xs text-muted-foreground hover:text-primary"
                        >
                          {concept.projectTitle}
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </TabsContent>
        </Tabs>
      )}
    </Page>
  );
}
