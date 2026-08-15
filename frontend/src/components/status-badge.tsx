import { Badge } from "@/components/ui/badge";
import type { ProjectStatus } from "@/types/project";
import { cn } from "@/lib/utils";

const NEUTRAL = "bg-muted text-muted-foreground border-transparent";
const WORKING = "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-transparent";
const THINKING = "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-transparent";
const BUILDING = "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-transparent";
const GOOD = "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-transparent";
const BAD = "bg-red-500/10 text-red-600 dark:text-red-400 border-transparent";

/** Labels are what a user would say, not what the pipeline calls it internally. */
const STATUS_CONFIG: Record<ProjectStatus, { label: string; className: string }> = {
  pending: { label: "Waiting for video", className: NEUTRAL },
  uploaded: { label: "Ready to process", className: NEUTRAL },
  processing: { label: "Reading your video", className: WORKING },
  transcribing: { label: "Listening to your video", className: WORKING },
  transcribed: { label: "Transcript ready", className: WORKING },
  analyzing: { label: "Understanding content", className: THINKING },
  analyzed: { label: "Content understood", className: THINKING },
  detecting_moments: { label: "Finding best moments", className: BUILDING },
  moments_ready: { label: "Best moments found", className: BUILDING },
  generating: { label: "Writing platform posts", className: BUILDING },
  completed: { label: "Campaign ready", className: GOOD },
  failed: { label: "Needs attention", className: BAD },
};

export function StatusBadge({ status }: { status: ProjectStatus }) {
  const config = STATUS_CONFIG[status] ?? { label: "In progress", className: NEUTRAL };
  return (
    <Badge className={cn("font-medium", config.className)}>{config.label}</Badge>
  );
}
