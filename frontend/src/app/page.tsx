"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  WifiOff,
  FolderOpen,
  Clapperboard,
  Megaphone,
  Film,
  ArrowRight,
} from "lucide-react";
import { UploadDropzone } from "@/components/upload-dropzone";
import { ProjectCard } from "@/components/project-card";
import { Page, PageHeader, SectionHeader, EmptyState } from "@/components/workspace";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { api } from "@/lib/api";
import type { ProjectSummary } from "@/types/project";

const API_ERROR =
  "Can't reach the RECAST API. Make sure the backend is running on the configured NEXT_PUBLIC_API_URL.";

/** Headline creation statistics, counted from real projects. */
function StatTile({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ElementType;
  value: number;
  label: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 transition-colors hover:border-primary/30">
      <div className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <Icon className="size-4" />
      </div>
      <p className="mt-4 text-3xl font-semibold leading-tight tabular-nums tracking-tight text-foreground">
        {value}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

export default function StudioPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      setProjects(await api.listProjects());
      setError(null);
    } catch {
      setError(API_ERROR);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .listProjects()
      .then((data) => {
        if (!cancelled) {
          setProjects(data);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError(API_ERROR);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const totals = (projects ?? []).reduce(
    (acc, p) => ({
      videos: acc.videos + (p.video_filename ? 1 : 0),
      shorts: acc.shorts + p.clip_count,
      posts: acc.posts + p.post_count,
    }),
    { videos: 0, shorts: 0, posts: 0 },
  );

  const recent = (projects ?? []).slice(0, 6);

  return (
    <Page className="space-y-12">
      {/* Hero */}
      <PageHeader
        eyebrow="AI Creative Studio"
        title={
          <>
            Turn one video into an
            <br className="hidden sm:block" /> entire content universe.
          </>
        }
        description="Upload once. RECAST transcribes it, learns what it is really about, finds the moments worth clipping, cuts vertical shorts with captions, and writes native copy for six platforms."
      />

      {error && (
        <Alert variant="destructive">
          <WifiOff className="size-4" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Upload — the single primary action on this page */}
      <section className="space-y-4">
        <SectionHeader
          title="Upload Content"
          description="Drop a video to start a new campaign."
        />
        <UploadDropzone
          onUploaded={(projectId) => {
            loadProjects();
            router.push(`/projects/${projectId}`);
          }}
        />
      </section>

      {/* Creation statistics */}
      {projects && projects.length > 0 && (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatTile icon={Film} value={totals.videos} label="Videos processed" />
          <StatTile
            icon={Clapperboard}
            value={totals.shorts}
            label="Shorts generated"
          />
          <StatTile icon={Megaphone} value={totals.posts} label="Posts created" />
        </section>
      )}

      {/* Recent work */}
      <section className="space-y-5">
        <SectionHeader
          title="Recent Projects"
          count={projects?.length}
          action={
            projects && projects.length > recent.length ? (
              <Button variant="ghost" size="sm" asChild>
                <Link href="/projects">
                  View all
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            ) : undefined
          }
        />

        {projects === null && !error && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-40 rounded-2xl" />
            ))}
          </div>
        )}

        {projects !== null && projects.length === 0 && (
          <EmptyState
            icon={FolderOpen}
            title="No projects yet"
            description="Upload your first video above — RECAST handles the transcript, the analysis, the clips and the full campaign."
          />
        )}

        {recent.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}
