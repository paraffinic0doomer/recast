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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";
import { countCampaignStats } from "@/lib/campaign-stats";
import type { Clip, PlatformKey, ProjectDetail } from "@/types/project";

const ACTIVE_STATUSES = new Set([
  "processing",
  "transcribing",
  "analyzing",
  "detecting_moments",
  "generating",
]);
const POLL_INTERVAL_MS = 2000;

/** Small count pill shown on a tab when that section has content. */
function TabCount({ n }: { n: number }) {
  return (
    <span className="ml-0.5 rounded bg-muted px-1.5 py-0.5 text-[0.6875rem] font-semibold tabular-nums text-muted-foreground">
      {n}
    </span>
  );
}

/** Placeholder for a tab whose stage has not run yet. */
function NotReadyYet({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-16 text-center">
      <Clock className="size-5 text-muted-foreground" />
      <p className="max-w-sm text-sm text-muted-foreground">{label}</p>
    </div>
  );
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
        await refresh();
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
      // Generation runs in the background; poll briefly for the result.
      for (let i = 0; i < 20; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        const updated = await api.getThumbnails(project.id);
        if (updated.concepts.length > 0) break;
      }
      await refresh();
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
      // Runs in the background; poll briefly for the new score.
      for (let i = 0; i < 20; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        const res = await api.getEvaluation(project.id);
        if (res.evaluation) break;
      }
      await refresh();
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
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-8 sm:gap-10 sm:px-6 sm:py-12">
      <Link
        href="/"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
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
        <div className="space-y-4">
          <Skeleton className="h-9 w-2/3" />
          <Skeleton className="h-40 rounded-xl" />
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
            <TabsList className="flex w-full flex-wrap">
              <TabsTrigger value="overview" className="gap-1.5">
                <LayoutDashboard className="size-3.5" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="campaign" className="gap-1.5">
                <Megaphone className="size-3.5" />
                Campaign
                {stats.platforms > 0 && <TabCount n={stats.platforms} />}
              </TabsTrigger>
              <TabsTrigger value="shorts" className="gap-1.5">
                <Clapperboard className="size-3.5" />
                Shorts
                {stats.shorts > 0 && <TabCount n={stats.shorts} />}
              </TabsTrigger>
              <TabsTrigger value="thumbnails" className="gap-1.5">
                <ImageIcon className="size-3.5" />
                Thumbnails
                {stats.thumbnails > 0 && <TabCount n={stats.thumbnails} />}
              </TabsTrigger>
              <TabsTrigger value="source" className="gap-1.5">
                <Dna className="size-3.5" />
                Source
              </TabsTrigger>
            </TabsList>

            {/* Overview \u2014 where the project is, and what to do next */}
            <TabsContent value="overview" className="mt-6 space-y-8">
              {project.content_dna && !project.platform_content && (
                <GenerateCampaignCta
                  isGenerating={project.status === "generating"}
                  onGenerate={() => handleGenerateCampaign()}
                />
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Progress</CardTitle>
                </CardHeader>
                <CardContent>
                  <PipelineSteps project={project} />
                </CardContent>
              </Card>
            </TabsContent>

            {/* Campaign \u2014 the main output */}
            <TabsContent value="campaign" className="mt-6 space-y-8">
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
            <TabsContent value="shorts" className="mt-6 space-y-8">
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

            <TabsContent value="thumbnails" className="mt-6">
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
            <TabsContent value="source" className="mt-6 space-y-8">
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
    </main>
  );
}
