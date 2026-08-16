"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  AlertCircle,
  Clapperboard,
  Clock,
  Dna,
  Image as ImageIcon,
  LayoutDashboard,
  Megaphone,
  RotateCw,
} from "lucide-react";
import { PipelineSteps } from "@/components/pipeline-steps";
import { TranscriptPanel } from "@/components/transcript-panel";
import { ContentDnaView } from "@/components/content-dna-view";
import { BestMomentsPanel } from "@/components/best-moments-panel";
import { ShortsSection } from "@/components/shorts-section";
import { CampaignPanel } from "@/components/campaign-panel";
import { ThumbnailSection } from "@/components/thumbnail-section";
import { CampaignScoreCard } from "@/components/campaign-score-card";
import { ProjectSummary } from "@/components/project-summary";
import { GenerateCampaignCta } from "@/components/generate-campaign-cta";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Page, SectionHeader, EmptyState } from "@/components/workspace";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";
import { countCampaignStats } from "@/lib/campaign-stats";
import { refreshAiEngine, formatRetry } from "@/lib/use-ai-engine";
import type { Clip, PlatformKey, ProjectDetail } from "@/types/project";

const ACTIVE_STATUSES = new Set([
  "processing",
  "transcribing",
  "analyzing",
  "detecting_moments",
  "generating",
]);
const POLL_INTERVAL_MS = 2000;

const POLL_STEP_MS = 1500;
/** Evaluation and thumbnails routinely take longer than 20s under load. */
const BACKGROUND_TIMEOUT_MS = 90000;

/**
 * Poll `check` until it reports done, or we run out of patience.
 * Returns whether the work actually produced a result.
 */
async function waitForResult(
  check: () => Promise<boolean>,
  timeoutMs = BACKGROUND_TIMEOUT_MS,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_STEP_MS));
    if (await check()) return true;
  }
  return false;
}

/**
 * Why a background generation produced nothing. The API accepts the request
 * and runs it detached, so a rate limit surfaces only as an absent result —
 * asking the engine for its state turns that into a sentence a user can act on.
 */
async function explainFailure(fallback: string): Promise<string> {
  const engine = await refreshAiEngine();
  if (engine.state === "rate_limited") {
    return `The AI engine has hit its daily token limit. All ${engine.keysTotal} keys are cooling down — try again in about ${formatRetry(engine.retryAfterSeconds)}.`;
  }
  if (engine.state === "offline") {
    return "The RECAST API is unreachable. Start the backend and try again.";
  }
  return fallback;
}

/** Small count pill shown on a tab when that section has content. */
function TabCount({ n }: { n: number }) {
  return (
    <span className="ml-1 rounded-md bg-foreground/10 px-1.5 py-0.5 font-mono text-[0.6875rem] tabular-nums text-current">
      {n}
    </span>
  );
}

/** Placeholder for a tab whose stage has not run yet. */
function NotReadyYet({ label }: { label: string }) {
  return <EmptyState icon={Clock} tone="pending" title="Not ready yet" description={label} />;
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [clips, setClips] = useState<Clip[]>([]);
  const [generatingMomentId, setGeneratingMomentId] = useState<string | null>(null);
  const [generatingPlatform, setGeneratingPlatform] = useState<PlatformKey | null>(null);
  const [isGeneratingThumbs, setIsGeneratingThumbs] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [tab, setTab] = useState("overview");
  const hasTriggeredProcess = useRef(false);
  const hasTriggeredAnalysis = useRef(false);
  const hasTriggeredMoments = useRef(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Counts shown on the tabs; safe before the project loads.
  const stats = project
    ? countCampaignStats(project)
    : { shorts: 0, platforms: 0, thumbnails: 0, moments: 0, assets: 0 };

  const refresh = useCallback(async () => {
    try {
      const data = await api.getProject(params.id);
      setProject(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load project");
      return null;
    }
  }, [params.id]);

  useEffect(() => {
    let cancelled = false;
    api
      .getProject(params.id)
      .then((data) => {
        if (!cancelled) {
          setProject(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Failed to load project",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  // Auto-start processing once a video has been uploaded but not yet processed.
  useEffect(() => {
    if (!project || hasTriggeredProcess.current) return;
    if (project.status === "uploaded") {
      hasTriggeredProcess.current = true;
      api
        .processProject(project.id)
        .then(() => refresh())
        .catch((err) => {
          setError(
            err instanceof ApiError ? err.message : "Failed to start processing",
          );
        });
    }
  }, [project, refresh]);

  // Chain into analysis automatically once a transcript exists.
  useEffect(() => {
    if (!project || hasTriggeredAnalysis.current) return;
    if (project.status === "transcribed" && project.transcript) {
      hasTriggeredAnalysis.current = true;
      api
        .analyzeProject(project.id)
        .then(() => refresh())
        .catch((err) => {
          setError(
            err instanceof ApiError ? err.message : "Failed to start analysis",
          );
        });
    }
  }, [project, refresh]);

  // Chain into moment detection once Content DNA exists.
  useEffect(() => {
    if (!project || hasTriggeredMoments.current) return;
    if (project.status === "analyzed" && project.content_dna) {
      hasTriggeredMoments.current = true;
      api
        .detectMoments(project.id)
        .then(() => refresh())
        .catch((err) => {
          setError(
            err instanceof ApiError ? err.message : "Failed to start moment detection",
          );
        });
    }
  }, [project, refresh]);

  // Poll while the pipeline is actively running.
  useEffect(() => {
    if (!project || !ACTIVE_STATUSES.has(project.status)) return;
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [project, refresh]);

  // Pick up clips rendered in an earlier session.
  useEffect(() => {
    if (!project?.best_moments?.length) return;
    api
      .getClips(project.id)
      .then((res) => setClips(res.clips))
      .catch(() => {
        /* listing clips is best-effort; the section still works without it */
      });
  }, [project?.id, project?.best_moments?.length]);

  const handleGenerateShort = useCallback(
    async (momentId: string) => {
      if (!project) return;
      setGeneratingMomentId(momentId);
      try {
        const clip = await api.createClip(project.id, momentId);
        setClips((prev) => [
          ...prev.filter((c) => c.moment_id !== momentId),
          clip,
        ]);
        toast.success("Short generated", {
          description: `${clip.width}x${clip.height} vertical clip is ready.`,
        });
      } catch (err) {
        toast.error("Couldn't generate short", {
          description:
            err instanceof ApiError ? err.message : "Clip rendering failed",
        });
      } finally {
        setGeneratingMomentId(null);
      }
    },
    [project],
  );

  const handleGenerateCampaign = useCallback(
    async (platform?: PlatformKey) => {
      if (!project) return;
      setGeneratingPlatform(platform ?? null);
      setTab("campaign");
      try {
        await api.generateCampaign(project.id, platform);

        // The request only queues the work, so wait for the content itself
        // rather than reporting success the moment the POST returns.
        const produced = await waitForResult(async () => {
          const fresh = await refresh();
          if (!fresh || fresh.status === "generating") return false;
          return platform
            ? Boolean(fresh.platform_content?.[platform])
            : Boolean(fresh.platform_content);
        });

        if (produced) {
          toast.success(
            platform ? `${platform} rewritten` : "Campaign ready",
          );
        } else {
          toast.error(
            platform
              ? `Couldn't write the ${platform} post`
              : "Couldn't generate campaign",
            { description: await explainFailure("The generator returned nothing. Try again in a moment.") },
          );
        }
      } catch (err) {
        toast.error("Couldn't generate campaign", {
          description:
            err instanceof ApiError ? err.message : "Campaign generation failed",
        });
      } finally {
        setGeneratingPlatform(null);
      }
    },
    [project, refresh],
  );

  const handleGenerateThumbnails = useCallback(async () => {
    if (!project) return;
    setIsGeneratingThumbs(true);
    try {
      await api.generateThumbnails(project.id);
      const produced = await waitForResult(async () => {
        const updated = await api.getThumbnails(project.id);
        return updated.concepts.length > 0;
      });
      await refresh();

      if (produced) {
        toast.success("Thumbnail concepts ready");
      } else {
        toast.error("Couldn't generate thumbnails", {
          description: await explainFailure("No concepts came back. Try again in a moment."),
        });
      }
    } catch (err) {
      toast.error("Couldn't generate thumbnails", {
        description:
          err instanceof ApiError ? err.message : "Thumbnail generation failed",
      });
    } finally {
      setIsGeneratingThumbs(false);
    }
  }, [project, refresh]);

  const handleEvaluate = useCallback(async () => {
    if (!project) return;
    setIsEvaluating(true);
    try {
      await api.evaluateCampaign(project.id);
      const scored = await waitForResult(async () => {
        const res = await api.getEvaluation(project.id);
        return Boolean(res.evaluation);
      });
      await refresh();

      if (scored) {
        toast.success("Campaign scored");
      } else {
        toast.error("Couldn't score campaign", {
          description: await explainFailure("The evaluator returned nothing. Try again in a moment."),
        });
      }
    } catch (err) {
      toast.error("Couldn't score campaign", {
        description:
          err instanceof ApiError ? err.message : "Evaluation failed",
      });
    } finally {
      setIsEvaluating(false);
    }
  }, [project, refresh]);

  const handleRetry = useCallback(async () => {
    if (!project) return;
    setIsRetrying(true);
    try {
      // Resume from the furthest stage that already succeeded, so a retry never
      // redoes expensive work that is already stored.
      if (project.content_dna) {
        hasTriggeredMoments.current = true;
        await api.detectMoments(project.id);
      } else if (project.transcript) {
        hasTriggeredAnalysis.current = true;
        await api.analyzeProject(project.id);
      } else {
        hasTriggeredProcess.current = true;
        await api.processProject(project.id);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Retry failed");
    } finally {
      setIsRetrying(false);
    }
  }, [project, refresh]);

  const handleSeek = useCallback((seconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = seconds;
    video.play().catch(() => {
      /* autoplay may be blocked; seeking still worked */
    });
  }, []);

  return (
    <Page className="space-y-8">
      <Link
        href="/projects"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to projects
      </Link>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Couldn&apos;t load project</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!project && !error && (
        <div className="space-y-6">
          <Skeleton className="h-10 w-2/3 rounded-xl" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,340px)_1fr]">
            <Skeleton className="aspect-video rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
          <Skeleton className="h-24 rounded-2xl" />
        </div>
      )}

      {project && (
        <>
          <ProjectSummary
            project={project}
            videoRef={videoRef}
            onTimeUpdate={setCurrentTime}
          />

          {project.status === "failed" && (
            <Alert variant="destructive">
              <AlertCircle className="size-4" />
              <AlertTitle>Processing stopped</AlertTitle>
              <AlertDescription className="space-y-3">
                <p>
                  {project.error_message ??
                    "Something went wrong while processing this video."}
                </p>
                <p className="text-xs opacity-80">
                  Your video and everything already generated were preserved.
                  You can retry without re-uploading.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRetry}
                  disabled={isRetrying}
                >
                  <RotateCw
                    className={isRetrying ? "size-3.5 animate-spin" : "size-3.5"}
                  />
                  {isRetrying ? "Retrying\u2026" : "Retry"}
                </Button>
              </AlertDescription>
            </Alert>
          )}

          <Tabs value={tab} onValueChange={setTab}>
            {/* Sticks to the top while scrolling: on a page this long the tab
                bar is the primary navigation, so it must never scroll away.
                The raised surface and ring lift it out of the surrounding
                text instead of letting it read as another row of labels. */}
            <div className="sticky top-14 z-30 -mx-5 bg-background/85 px-5 py-3 backdrop-blur sm:-mx-8 sm:px-8 lg:top-0">
              <TabsList className="flex h-auto w-full flex-wrap gap-1 rounded-xl border border-border bg-surface p-1.5 shadow-sm">
                <TabsTrigger value="overview" className="gap-2 px-3.5 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-primary dark:data-[state=active]:text-primary-foreground">
                  <LayoutDashboard className="size-4" />
                  Overview
                </TabsTrigger>
                <TabsTrigger value="campaign" className="gap-2 px-3.5 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-primary dark:data-[state=active]:text-primary-foreground">
                  <Megaphone className="size-4" />
                  Campaign
                  {stats.platforms > 0 && <TabCount n={stats.platforms} />}
                </TabsTrigger>
                <TabsTrigger value="shorts" className="gap-2 px-3.5 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-primary dark:data-[state=active]:text-primary-foreground">
                  <Clapperboard className="size-4" />
                  Shorts
                  {stats.shorts > 0 && <TabCount n={stats.shorts} />}
                </TabsTrigger>
                <TabsTrigger value="thumbnails" className="gap-2 px-3.5 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-primary dark:data-[state=active]:text-primary-foreground">
                  <ImageIcon className="size-4" />
                  Thumbnails
                  {stats.thumbnails > 0 && <TabCount n={stats.thumbnails} />}
                </TabsTrigger>
                <TabsTrigger value="source" className="gap-2 px-3.5 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-primary dark:data-[state=active]:text-primary-foreground">
                  <Dna className="size-4" />
                  Source
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Overview \u2014 where the project is, and what to do next */}
            <TabsContent value="overview" className="mt-8 space-y-8">
              {project.content_dna && !project.platform_content && (
                <GenerateCampaignCta
                  isGenerating={project.status === "generating"}
                  onGenerate={() => handleGenerateCampaign()}
                />
              )}

              <section className="space-y-5">
                <SectionHeader
                  title="AI Pipeline"
                  description="Every stage RECAST runs on your video, and where it is right now."
                />
                <div className="rounded-2xl border border-border bg-card p-6 sm:p-7">
                  <PipelineSteps project={project} />
                </div>
              </section>
            </TabsContent>

            {/* Campaign \u2014 the main output */}
            <TabsContent value="campaign" className="mt-8 space-y-10">
              {project.content_dna ? (
                <>
                  <CampaignPanel
                    campaign={project.platform_content}
                    campaignScore={project.campaign_score}
                    isGenerating={project.status === "generating"}
                    generatingPlatform={generatingPlatform}
                    onGenerate={handleGenerateCampaign}
                  />
                  {project.platform_content && (
                    <CampaignScoreCard
                      evaluation={project.campaign_evaluation}
                      completenessScore={project.campaign_score}
                      isEvaluating={isEvaluating}
                      onEvaluate={handleEvaluate}
                      hasCampaign={Boolean(project.platform_content)}
                    />
                  )}
                </>
              ) : (
                <NotReadyYet label="The campaign is written once RECAST has understood the video." />
              )}
            </TabsContent>

            {/* Shorts \u2014 clips and the moments they came from */}
            <TabsContent value="shorts" className="mt-8 space-y-10">
              {project.best_moments && project.best_moments.length > 0 ? (
                <>
                  <ShortsSection
                    projectId={project.id}
                    moments={project.best_moments}
                    initialClips={clips}
                  />
                  <BestMomentsPanel
                    moments={project.best_moments}
                    onSeek={handleSeek}
                    generatedMomentIds={new Set(clips.map((c) => c.moment_id))}
                    generatingMomentId={generatingMomentId}
                    onGenerateShort={handleGenerateShort}
                  />
                </>
              ) : (
                <NotReadyYet label="Best moments appear once the video has been analysed." />
              )}
            </TabsContent>

            <TabsContent value="thumbnails" className="mt-8">
              {project.content_dna ? (
                <ThumbnailSection
                  concepts={project.thumbnail_concepts ?? []}
                  isGenerating={isGeneratingThumbs}
                  onGenerate={handleGenerateThumbnails}
                />
              ) : (
                <NotReadyYet label="Thumbnail concepts need the video's Content DNA first." />
              )}
            </TabsContent>

            {/* Source \u2014 what everything else was built from */}
            <TabsContent value="source" className="mt-8 space-y-10">
              {project.content_dna && (
                <ContentDnaView dna={project.content_dna} onSeek={handleSeek} />
              )}
              {project.transcript && (
                <TranscriptPanel
                  transcript={project.transcript}
                  onSeek={handleSeek}
                  currentTime={currentTime}
                />
              )}
              {!project.content_dna && !project.transcript && (
                <NotReadyYet label="The transcript and Content DNA appear once processing finishes." />
              )}
            </TabsContent>
          </Tabs>
        </>
      )}
    </Page>
  );
}
