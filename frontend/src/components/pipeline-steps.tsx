"use client";

import {
  Check,
  AlertCircle,
  UploadCloud,
  BrainCircuit,
  Sparkles,
  Clapperboard,
  Megaphone,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AiThinking } from "@/components/ai-thinking";
import type { ProjectDetail } from "@/types/project";

type StepState = "done" | "active" | "error" | "upcoming";

interface Step {
  key: string;
  label: string;
  icon: React.ElementType;
  /** What is happening, in plain language, while this step runs. */
  running: string;
  /** What the user got once it finished. */
  done: string;
}

/** The five beats of the pipeline, told in the user's language. */
const STEPS: Step[] = [
  {
    key: "upload",
    label: "Upload",
    icon: UploadCloud,
    running: "Saving your video",
    done: "Video received and inspected",
  },
  {
    key: "understand",
    label: "Understanding",
    icon: BrainCircuit,
    running: "Listening to your video and reading what it means",
    done: "Topic, audience, tone and core message identified",
  },
  {
    key: "moments",
    label: "Finding Moments",
    icon: Sparkles,
    running: "Scoring every segment for clip potential",
    done: "Strongest moments selected and ranked",
  },
  {
    key: "shorts",
    label: "Generating Shorts",
    icon: Clapperboard,
    running: "Cutting vertical clips with burned-in captions",
    done: "Vertical shorts rendered",
  },
  {
    key: "campaign",
    label: "Building Campaign",
    icon: Megaphone,
    running: "Writing native copy for each platform",
    done: "Six platforms written and ready to publish",
  },
];

function computeStepStates(project: ProjectDetail): Record<string, StepState> {
  const hasVideo = Boolean(project.video_filename);
  const hasDna = Boolean(project.content_dna);
  const hasMoments = Boolean(project.best_moments?.length);
  const hasShorts = Boolean(project.clips?.length);
  const hasCampaign = Boolean(project.platform_content);

  const failed = project.status === "failed";
  const status = project.status;

  // A step only owns the failure if everything before it actually succeeded.
  const errorAt = (previousDone: boolean, thisDone: boolean) =>
    failed && previousDone && !thisDone;

  return {
    upload: hasVideo ? "done" : failed ? "error" : "active",
    understand: hasDna
      ? "done"
      : errorAt(hasVideo, hasDna)
        ? "error"
        : status === "processing" ||
            status === "transcribing" ||
            status === "transcribed" ||
            status === "analyzing"
          ? "active"
          : "upcoming",
    moments: hasMoments
      ? "done"
      : errorAt(hasDna, hasMoments)
        ? "error"
        : status === "detecting_moments" || status === "analyzed"
          ? "active"
          : "upcoming",
    shorts: hasShorts ? "done" : "upcoming",
    campaign: hasCampaign
      ? "done"
      : errorAt(hasMoments, hasCampaign)
        ? "error"
        : status === "generating"
          ? "active"
          : "upcoming",
  };
}

/** Fraction of the pipeline completed, for the header progress bar. */
function completion(states: Record<string, StepState>) {
  const done = STEPS.filter((s) => states[s.key] === "done").length;
  return Math.round((done / STEPS.length) * 100);
}

function StepMedallion({
  state,
  icon: Icon,
}: {
  state: StepState;
  icon: React.ElementType;
}) {
  const base =
    "relative flex size-11 shrink-0 items-center justify-center rounded-2xl transition-all duration-300";

  if (state === "done")
    return (
      <div className={cn(base, "bg-success/12 text-success ring-1 ring-success/30")}>
        <Check className="size-5" />
      </div>
    );

  if (state === "active")
    return (
      <div className={cn(base, "bg-primary/12 text-primary ai-glow")}>
        <span className="absolute inset-0 overflow-hidden rounded-2xl ai-shimmer" />
        <Icon className="relative size-5" />
      </div>
    );

  if (state === "error")
    return (
      <div className={cn(base, "bg-destructive/12 text-destructive ring-1 ring-destructive/30")}>
        <AlertCircle className="size-5" />
      </div>
    );

  return (
    <div className={cn(base, "bg-secondary/60 text-muted-foreground ring-1 ring-border")}>
      <Icon className="size-5" />
    </div>
  );
}

/**
 * The AI pipeline, as a vertical run of stages. Each stage carries its own
 * icon, state and progress, and the running stage narrates itself — this is
 * the screen a judge watches while the video is being processed.
 */
export function PipelineSteps({ project }: { project: ProjectDetail }) {
  const states = computeStepStates(project);
  const percent = completion(states);

  return (
    <div className="space-y-6">
      {/* Overall progress */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Pipeline progress
          </span>
          <span className="font-mono text-sm tabular-nums text-foreground">
            {percent}%
          </span>
        </div>
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-secondary"
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Pipeline progress"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      <ol className="space-y-0">
        {STEPS.map((step, index) => {
          const state = states[step.key];
          const isLast = index === STEPS.length - 1;
          return (
            <li key={step.key} className="flex gap-4">
              <div className="flex flex-col items-center">
                <StepMedallion state={state} icon={step.icon} />
                {!isLast && (
                  <div
                    className={cn(
                      "min-h-8 w-px flex-1 transition-colors duration-500",
                      state === "done" ? "bg-success/40" : "bg-border",
                    )}
                  />
                )}
              </div>

              <div className={cn("min-w-0 flex-1 pb-7 pt-1.5", isLast && "pb-0")}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <p
                    className={cn(
                      "text-[0.95rem] font-semibold leading-tight",
                      state === "upcoming" ? "text-muted-foreground" : "text-foreground",
                    )}
                  >
                    {step.label}
                  </p>
                  {state === "active" && (
                    <span className="rounded-md bg-primary/12 px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-wider text-primary">
                      Running
                    </span>
                  )}
                  {state === "done" && (
                    <span className="rounded-md bg-success/12 px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-wider text-success">
                      Done
                    </span>
                  )}
                  {state === "error" && (
                    <span className="rounded-md bg-destructive/12 px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-wider text-destructive">
                      Stopped
                    </span>
                  )}
                </div>

                {state === "active" ? (
                  <AiThinking
                    status={project.status}
                    fallback={step.running}
                    className="mt-1.5"
                  />
                ) : (
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {state === "done"
                      ? step.done
                      : state === "error"
                        ? "Stopped here — the message below explains why."
                        : step.running}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
