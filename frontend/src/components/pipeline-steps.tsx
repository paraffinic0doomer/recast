import { Check, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProjectDetail } from "@/types/project";

type StepState = "done" | "active" | "error" | "upcoming";

interface Step {
  key: string;
  label: string;
  /** What is happening, in plain language, while this step runs. */
  running: string;
  /** What the user got once it finished. */
  done: string;
}

/**
 * The story RECAST tells, in the user's language rather than the pipeline's.
 * Six beats, matching what actually happens to their video.
 */
const STEPS: Step[] = [
  {
    key: "upload",
    label: "Upload",
    running: "Saving your video",
    done: "Video uploaded",
  },
  {
    key: "understand",
    label: "AI Understands",
    running: "Listening to your video and reading the content",
    done: "Topic, audience and core message identified",
  },
  {
    key: "moments",
    label: "Finds Best Moments",
    running: "Scoring every segment for clip potential",
    done: "Strongest moments selected and ranked",
  },
  {
    key: "shorts",
    label: "Creates Shorts",
    running: "Cutting vertical clips",
    done: "Vertical shorts rendered",
  },
  {
    key: "platforms",
    label: "Adapts to Platforms",
    running: "Writing native copy for each platform",
    done: "Platform posts written",
  },
  {
    key: "ready",
    label: "Campaign Ready",
    running: "Finishing up",
    done: "Everything is ready to publish",
  },
];

function computeStepStates(project: ProjectDetail): Record<string, StepState> {
  const hasVideo = Boolean(project.video_filename);
  const hasDna = Boolean(project.content_dna);
  const hasMoments = Boolean(project.best_moments?.length);
  const hasShorts = Boolean(project.clips?.length);
  const hasCampaign = Boolean(project.platform_content);
  const isReady = project.status === "completed" && hasCampaign;

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
            status === "analyzing"
          ? "active"
          : "upcoming",
    moments: hasMoments
      ? "done"
      : errorAt(hasDna, hasMoments)
        ? "error"
        : status === "detecting_moments"
          ? "active"
          : "upcoming",
    shorts: hasShorts ? "done" : "upcoming",
    platforms: hasCampaign
      ? "done"
      : errorAt(hasMoments, hasCampaign)
        ? "error"
        : status === "generating"
          ? "active"
          : "upcoming",
    ready: isReady ? "done" : "upcoming",
  };
}

function StepIcon({ state, index }: { state: StepState; index: number }) {
  const base = "flex size-8 shrink-0 items-center justify-center rounded-full";
  if (state === "done")
    return (
      <div className={cn(base, "bg-emerald-500 text-white")}>
        <Check className="size-4" />
      </div>
    );
  if (state === "active")
    return (
      <div className={cn(base, "bg-primary text-primary-foreground")}>
        <Loader2 className="size-4 animate-spin" />
      </div>
    );
  if (state === "error")
    return (
      <div className={cn(base, "bg-red-500 text-white")}>
        <AlertCircle className="size-4" />
      </div>
    );
  return (
    <div
      className={cn(
        base,
        "border-2 border-border bg-background text-xs font-medium text-muted-foreground",
      )}
    >
      {index + 1}
    </div>
  );
}

/** Vertical timeline — reads as a story at any screen size. */
export function PipelineSteps({ project }: { project: ProjectDetail }) {
  const states = computeStepStates(project);

  return (
    <ol className="space-y-0">
      {STEPS.map((step, index) => {
        const state = states[step.key];
        const isLast = index === STEPS.length - 1;
        return (
          <li key={step.key} className="flex gap-4">
            <div className="flex flex-col items-center">
              <StepIcon state={state} index={index} />
              {!isLast && (
                <div
                  className={cn(
                    "min-h-6 w-px flex-1",
                    state === "done" ? "bg-emerald-500/40" : "bg-border",
                  )}
                />
              )}
            </div>

            <div className={cn("min-w-0 pb-5", isLast && "pb-0")}>
              <p
                className={cn(
                  "text-sm font-semibold leading-tight",
                  state === "done" && "text-foreground",
                  state === "active" && "text-primary",
                  state === "error" && "text-red-600 dark:text-red-400",
                  state === "upcoming" && "text-muted-foreground",
                )}
              >
                {step.label}
              </p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {state === "done"
                  ? step.done
                  : state === "error"
                    ? "Stopped here — see the message below"
                    : step.running}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
