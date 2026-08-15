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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/status-badge";
import { CampaignOverview } from "@/components/campaign-overview";
import { mediaUrl } from "@/lib/api";
import { formatFileSize, cn } from "@/lib/utils";
import {
  buildCampaignExport,
  countCampaignStats,
  downloadText,
} from "@/lib/campaign-stats";
import { toast } from "sonner";
import type { ProjectDetail } from "@/types/project";

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
    downloadText(`${slugify(project.title)}-campaign.txt`, buildCampaignExport(project));
    toast.success("Campaign downloaded");
  }, [project]);

  return (
    <Card className={cn(isReady && "border-emerald-500/40")}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <CardTitle className="text-xl">{project.title}</CardTitle>
            <p className="truncate text-sm text-muted-foreground">
              {project.video_filename ?? "No video attached"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={project.status} />
            {project.campaign_evaluation && (
              <Badge variant="secondary" className="font-medium tabular-nums">
                Quality {project.campaign_evaluation.overall}/100
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-8">
        {/* Campaign ready banner */}
        {isReady && (
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-5 py-4">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="size-5" />
            </div>
            <div className="min-w-[14rem] flex-1">
              <p className="font-semibold text-foreground">Campaign ready</p>
              <p className="text-sm text-muted-foreground">
                Everything is ready to publish — {stats.assets} content assets
                across {stats.platforms} platforms.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={handleCopyAll}>
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "Copied" : "Copy all"}
              </Button>
              <Button size="sm" onClick={handleDownload}>
                <Download className="size-3.5" />
                Download campaign
              </Button>
            </div>
          </div>
        )}

        {/* video + key facts */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,320px)_1fr]">
          <div className="space-y-2">
            {project.video_url ? (
              <video
                ref={videoRef}
                controls
                preload="metadata"
                src={mediaUrl(project.video_url)}
                onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
                className="w-full rounded-lg border bg-black"
              />
            ) : (
              <div className="flex aspect-video w-full items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                No video
              </div>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {project.duration_seconds != null && (
                <span className="flex items-center gap-1">
                  <Clock className="size-3" />
                  {formatDuration(project.duration_seconds)}
                </span>
              )}
              {project.video_width != null && project.video_height != null && (
                <span className="flex items-center gap-1">
                  <Maximize2 className="size-3" />
                  {project.video_width}×{project.video_height}
                </span>
              )}
              {project.video_size_bytes != null && (
                <span className="flex items-center gap-1">
                  <HardDrive className="size-3" />
                  {formatFileSize(project.video_size_bytes)}
                </span>
              )}
            </div>
          </div>

          {/* Content DNA summary */}
          <div className="space-y-3">
            {dna ? (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    { label: "Type", value: dna.content_type },
                    { label: "Audience", value: dna.audience },
                    { label: "Tone", value: dna.tone },
                    { label: "Topic", value: dna.primary_topic },
                  ].map((item) => (
                    <div key={item.label} className="min-w-0">
                      <p className="text-[0.6875rem] font-semibold uppercase tracking-wider text-muted-foreground">
                        {item.label}
                      </p>
                      <p className="truncate text-sm font-medium text-foreground" title={item.value}>
                        {item.value || "—"}
                      </p>
                    </div>
                  ))}
                </div>
                {dna.core_message && (
                  <div className="rounded-lg border-l-2 border-primary bg-muted/40 px-4 py-2.5">
                    <p className="text-[0.6875rem] font-semibold uppercase tracking-wider text-muted-foreground">
                      Core message
                    </p>
                    <p className="mt-0.5 text-sm leading-relaxed text-foreground">
                      {dna.core_message}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="flex h-full min-h-24 flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed p-4 text-center">
                <Sparkles className="size-4 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Content DNA appears once analysis finishes.
                </p>
              </div>
            )}
          </div>
        </div>

        <Separator />

        <CampaignOverview
          stats={stats}
          hasVideo={Boolean(project.video_filename)}
          hasDna={Boolean(dna)}
        />
      </CardContent>
    </Card>
  );
}
