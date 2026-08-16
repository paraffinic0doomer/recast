import Link from "next/link";
import { StatusBadge } from "@/components/status-badge";
import { Film, Clapperboard, Megaphone, Dna, ArrowUpRight } from "lucide-react";
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
    <span className="flex items-center gap-1.5" title={label}>
      <Icon className="size-3.5 text-muted-foreground" />
      <span className="font-mono text-xs tabular-nums text-foreground">{value}</span>
    </span>
  );
}

export function ProjectCard({ project }: { project: ProjectSummary }) {
  const hasOutput =
    project.has_content_dna || project.clip_count > 0 || project.post_count > 0;

  return (
    <Link href={`/projects/${project.id}`} className="group block h-full">
      <article className="flex h-full flex-col justify-between gap-5 rounded-2xl border border-border bg-card p-5 transition-all duration-200 group-hover:border-primary/40 group-hover:bg-surface">
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-muted-foreground transition-colors group-hover:bg-primary/10 group-hover:text-primary">
              <Film className="size-4" />
            </span>
            <ArrowUpRight className="size-4 shrink-0 text-muted-foreground opacity-0 transition-all group-hover:opacity-100" />
          </div>

          <div className="min-w-0 space-y-1">
            <h3 className="line-clamp-2 text-[0.95rem] font-semibold leading-snug text-foreground">
              {project.title}
            </h3>
            <p className="truncate text-xs text-muted-foreground">
              {project.video_filename ?? "No video attached"}
            </p>
          </div>

          <StatusBadge status={project.status} />
        </div>

        <div className="space-y-3 border-t border-border pt-4">
          {hasOutput && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
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

          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{formatDate(project.created_at)}</span>
            {project.campaign_score != null && (
              <span className="font-mono tabular-nums text-foreground">
                {/* The API can return a fractional score; a card is no place
                    for decimals. */}
                {Math.round(project.campaign_score)}/100
              </span>
            )}
          </div>
        </div>
      </article>
    </Link>
  );
}
