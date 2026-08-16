import type { ProjectStatus } from "@/types/project";
import { cn } from "@/lib/utils";

const NEUTRAL = "bg-secondary text-muted-foreground";
const WORKING = "bg-primary/12 text-primary";
const GOOD = "bg-success/12 text-success";
const BAD = "bg-destructive/12 text-destructive";

/** Labels are what a user would say, not what the pipeline calls it internally. */
const STATUS_CONFIG: Record<
  ProjectStatus,
  { label: string; className: string; live?: boolean }
> = {
  pending: { label: "Waiting for video", className: NEUTRAL },
  uploaded: { label: "Ready to process", className: NEUTRAL },
  processing: { label: "Reading your video", className: WORKING, live: true },
  transcribing: { label: "Listening", className: WORKING, live: true },
  transcribed: { label: "Transcript ready", className: WORKING },
  analyzing: { label: "Understanding", className: WORKING, live: true },
  analyzed: { label: "Content understood", className: WORKING },
  detecting_moments: { label: "Finding moments", className: WORKING, live: true },
  moments_ready: { label: "Moments found", className: WORKING },
  generating: { label: "Writing posts", className: WORKING, live: true },
  completed: { label: "Campaign ready", className: GOOD },
  failed: { label: "Needs attention", className: BAD },
};

export function StatusBadge({
  status,
  className,
}: {
  status: ProjectStatus;
  className?: string;
}) {
  const config = STATUS_CONFIG[status] ?? { label: "In progress", className: NEUTRAL };

  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium",
        config.className,
        className,
      )}
    >
      {/* A live stage gets a pulsing dot, so "still working" is visible at a glance. */}
      {config.live && <span className="size-1.5 rounded-full bg-current ai-pulse" />}
      {config.label}
    </span>
  );
}
