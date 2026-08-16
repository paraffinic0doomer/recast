"use client";

import Link from "next/link";
import { WifiOff, Megaphone, ArrowRight, Sparkles } from "lucide-react";
import { Page, PageHeader, EmptyState } from "@/components/workspace";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useProjects } from "@/lib/use-projects";
import { ScoreRing } from "@/components/score-ring";
import { HIDE_LIBRARY } from "@/lib/visibility";
import { PrivateLibrary } from "@/components/private-library";

export default function CampaignsPage() {
  const { projects, error } = useProjects();

  // A campaign exists once at least one platform post has been written.
  const withCampaign = (projects ?? []).filter((p) => p.post_count > 0);
  const awaiting = (projects ?? []).filter(
    (p) => p.post_count === 0 && p.has_content_dna,
  );

  const totalPosts = withCampaign.reduce((sum, p) => sum + p.post_count, 0);

  // Hooks above run either way; only the listing is withheld.
  if (HIDE_LIBRARY) {
    return (
      <Page className="space-y-8">
        <PageHeader
          eyebrow="Workspace"
          title="Campaigns"
          description="Generated campaigns live here once RECAST has written copy for your platforms."
        />
        <PrivateLibrary what="Campaigns" />
      </Page>
    );
  }

  return (
    <Page className="space-y-8">
      <PageHeader
        eyebrow="Workspace"
        title="Campaigns"
        description={
          withCampaign.length > 0
            ? `${totalPosts} platform posts across ${withCampaign.length} ${withCampaign.length === 1 ? "campaign" : "campaigns"}, each written natively for its platform.`
            : "Generated campaigns appear here once RECAST has written copy for your platforms."
        }
      />

      {error && (
        <Alert variant="destructive">
          <WifiOff className="size-4" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {projects === null && !error && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-2xl" />
          ))}
        </div>
      )}

      {projects !== null && withCampaign.length === 0 && awaiting.length === 0 && (
        <EmptyState
          icon={Megaphone}
          title="No campaigns yet"
          description="Upload a video and let RECAST understand it — then one click writes copy for all six platforms."
          action={
            <Button asChild>
              <Link href="/">Go to Studio</Link>
            </Button>
          }
        />
      )}

      {withCampaign.length > 0 && (
        <div className="space-y-3">
          {withCampaign.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="group flex flex-wrap items-center gap-x-6 gap-y-4 rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary/40"
            >
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Megaphone className="size-5" />
              </div>

              <div className="min-w-[12rem] flex-1">
                <p className="line-clamp-1 text-[0.95rem] font-semibold text-foreground">
                  {project.title}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {project.post_count} platform{" "}
                  {project.post_count === 1 ? "post" : "posts"}
                  {project.clip_count > 0 &&
                    ` · ${project.clip_count} ${project.clip_count === 1 ? "short" : "shorts"}`}
                </p>
              </div>

              <StatusBadge status={project.status} />

              {project.campaign_score != null && (
                <ScoreRing value={project.campaign_score} size={44} label="Score" />
              )}

              <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
            </Link>
          ))}
        </div>
      )}

      {/* Projects that are understood but not yet turned into a campaign —
          the highest-value next action in the whole product. */}
      {awaiting.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            Ready to generate
          </h2>
          {awaiting.map((project) => (
            <div
              key={project.id}
              className="flex flex-wrap items-center gap-x-6 gap-y-4 rounded-2xl border border-dashed border-primary/30 bg-primary/[0.04] p-5"
            >
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Sparkles className="size-5" />
              </div>
              <div className="min-w-[12rem] flex-1">
                <p className="line-clamp-1 text-[0.95rem] font-semibold text-foreground">
                  {project.title}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Content DNA is ready — no campaign written yet.
                </p>
              </div>
              <Button asChild>
                <Link href={`/projects/${project.id}`}>
                  Generate campaign
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          ))}
        </section>
      )}
    </Page>
  );
}
