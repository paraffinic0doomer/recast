"use client";

import { useCallback, useState } from "react";
import {
  Clock,
  Maximize2,
  HardDrive,
  CheckCircle2,
  Download,
  Copy,
  Check,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { CampaignOverview } from "@/components/campaign-overview";
import { FieldLabel } from "@/components/workspace";
import { ScoreRing } from "@/components/score-ring";
import { AiThinking } from "@/components/ai-thinking";
import { mediaUrl } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import {
  buildCampaignExport,
  countCampaignStats,
  downloadText,
} from "@/lib/campaign-stats";
import { toast } from "sonner";
import type { ProjectDetail } from "@/types/project";

const ACTIVE_STATUSES = new Set([
  "processing",
  "transcribing",
  "analyzing",
  "detecting_moments",
  "generating",
]);

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function slugify(value: string) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "campaign"
  );
}

interface ProjectSummaryProps {
  project: ProjectDetail;
  /** Lets the transcript highlight the segment currently playing. */
  onTimeUpdate?: (seconds: number) => void;
  videoRef?: React.Ref<HTMLVideoElement>;
}

export function ProjectSummary({
  project,
  onTimeUpdate,
  videoRef,
}: ProjectSummaryProps) {
  const [copied, setCopied] = useState(false);
  const stats = countCampaignStats(project);
  const isReady = project.status === "completed" && stats.platforms > 0;
  const isWorking = ACTIVE_STATUSES.has(project.status);
  const dna = project.content_dna;

  const handleCopyAll = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(buildCampaignExport(project));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success("Campaign copied", {
        description: "The full campaign is on your clipboard.",
      });
    } catch {
      toast.error("Couldn't copy", { description: "Clipboard access was blocked." });
    }
  }, [project]);

  const handleDownload = useCallback(() => {
    downloadText(
      `${slugify(project.title)}-campaign.txt`,
      buildCampaignExport(project),
    );
    toast.success("Campaign downloaded");
  }, [project]);

  return (
    <section className="space-y-8">
      {/* Title row */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0 flex-1 space-y-2">
          <h1 className="text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl">
            {project.title}
          </h1>
          <p className="break-all font-mono text-xs text-muted-foreground">
            {project.video_filename ?? "No video attached"}
          </p>
          {isWorking && <AiThinking status={project.status} className="pt-1" />}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={project.status} />
          {project.campaign_evaluation && (
            <ScoreRing
              value={project.campaign_evaluation.overall}
              size={64}
              label="Quality"
            />
          )}
        </div>
      </div>

      {/* Campaign ready banner — the demo's payoff moment */}
      {isReady && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-4 rounded-2xl border border-success/30 bg-success/[0.06] px-6 py-5">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-success/15 text-success">
            <CheckCircle2 className="size-5" />
          </span>
          <div className="min-w-[14rem] flex-1">
            <p className="text-[1.05rem] font-semibold text-foreground">
              Your campaign is ready
            </p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {stats.assets} content assets across {stats.platforms} platforms,
              all written from this video.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleCopyAll}>
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              {copied ? "Copied" : "Copy all"}
            </Button>
            <Button onClick={handleDownload}>
              <Download className="size-4" />
              Download campaign
            </Button>
          </div>
        </div>
      )}

      {/* Video + what the AI understood */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,340px)_1fr]">
        <div className="space-y-3">
          {project.video_url ? (
            <video
              ref={videoRef}
              controls
              preload="metadata"
              src={mediaUrl(project.video_url)}
              onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
              className="w-full rounded-2xl border border-border bg-black"
            />
          ) : (
            <div className="flex aspect-video w-full items-center justify-center rounded-2xl border border-dashed border-border text-sm text-muted-foreground">
              No video
            </div>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 font-mono text-xs text-muted-foreground">
            {project.duration_seconds != null && (
              <span className="flex items-center gap-1.5">
                <Clock className="size-3" />
                {formatDuration(project.duration_seconds)}
              </span>
            )}
            {project.video_width != null && project.video_height != null && (
              <span className="flex items-center gap-1.5">
                <Maximize2 className="size-3" />
                {project.video_width}×{project.video_height}
              </span>
            )}
            {project.video_size_bytes != null && (
              <span className="flex items-center gap-1.5">
                <HardDrive className="size-3" />
                {formatFileSize(project.video_size_bytes)}
              </span>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {dna ? (
            <>
              {/* Phrases, not labels — two columns so they wrap rather than clip. */}
              <div className="grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2">
                {[
                  { label: "Type", value: dna.content_type },
                  { label: "Audience", value: dna.audience },
                  { label: "Tone", value: dna.tone },
                  { label: "Topic", value: dna.primary_topic },
                ].map((item) => (
                  <div key={item.label} className="min-w-0">
                    <FieldLabel>{item.label}</FieldLabel>
                    <p className="mt-1.5 text-sm font-medium leading-snug text-foreground">
                      {item.value || "—"}
                    </p>
                  </div>
                ))}
              </div>

              {dna.core_message && (
                <div className="rounded-xl border-l-2 border-primary bg-surface px-4 py-3.5">
                  <FieldLabel>Core message</FieldLabel>
                  <p className="mt-1.5 text-[0.95rem] leading-relaxed text-foreground">
                    {dna.core_message}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border px-4 py-8 text-center">
              <Sparkles className="size-5 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Content DNA appears once RECAST has understood your video.
              </p>
            </div>
          )}
        </div>
      </div>

      <CampaignOverview
        stats={stats}
        hasVideo={Boolean(project.video_filename)}
        hasDna={Boolean(dna)}
      />
    </section>
  );
}
