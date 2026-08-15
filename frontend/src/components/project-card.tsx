import Link from "next/link";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { Film, Clapperboard, Megaphone, Dna } from "lucide-react";
import type { ProjectSummary } from "@/types/project";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function Stat({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ElementType;
  value: number | string;
  label: string;
}) {
  return (
    <span className="flex items-center gap-1" title={label}>
      <Icon className="size-3" />
      <span className="tabular-nums">{value}</span>
    </span>
  );
}

export function ProjectCard({ project }: { project: ProjectSummary }) {
  const hasOutput =
    project.has_content_dna || project.clip_count > 0 || project.post_count > 0;

  return (
    <Link href={`/projects/${project.id}`} className="group block h-full">
      <Card className="h-full transition-colors group-hover:border-primary/40 group-hover:shadow-sm">
        <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Film className="size-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium leading-tight">
                {project.title}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {project.video_filename ?? "No video attached"}
              </p>
            </div>
          </div>
          <StatusBadge status={project.status} />
        </CardHeader>

        <CardContent className="space-y-3">
          {hasOutput && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {project.has_content_dna && (
                <Stat icon={Dna} value="DNA" label="Content DNA ready" />
              )}
              <Stat
                icon={Clapperboard}
                value={project.clip_count}
                label="Shorts generated"
              />
              <Stat
                icon={Megaphone}
                value={project.post_count}
                label="Platform posts"
              />
            </div>
          )}

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{formatDate(project.created_at)}</span>
            {project.campaign_score != null && (
              <span className="font-medium text-foreground tabular-nums">
                {project.campaign_score}/100
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
