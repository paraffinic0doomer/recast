"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, WifiOff, FolderOpen, Clapperboard, Megaphone } from "lucide-react";
import { UploadDropzone } from "@/components/upload-dropzone";
import { ProjectCard } from "@/components/project-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { api } from "@/lib/api";
import type { ProjectSummary } from "@/types/project";

const API_ERROR =
  "Can't reach the RECAST API. Make sure the backend is running on the configured NEXT_PUBLIC_API_URL.";

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
    <div className="flex items-center gap-3 rounded-xl border bg-card px-4 py-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Icon className="size-4" />
      </div>
      <div>
        <p className="text-xl font-semibold leading-none tabular-nums text-foreground">
          {value}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data);
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
      shorts: acc.shorts + p.clip_count,
      posts: acc.posts + p.post_count,
    }),
    { shorts: 0, posts: 0 },
  );

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-4 py-12 sm:gap-12 sm:px-6 sm:py-16">
      <header className="space-y-3 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Sparkles className="size-6" />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          RECAST
        </h1>
        <p className="mx-auto max-w-xl text-balance text-muted-foreground">
          One piece of content. An entire campaign. Upload a video and RECAST
          turns it into shorts, platform-native posts, thumbnails and SEO — in
          one pass.
        </p>
      </header>

      {error && (
        <Alert variant="destructive">
          <WifiOff className="size-4" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Upload Content</CardTitle>
        </CardHeader>
        <CardContent>
          <UploadDropzone
            onUploaded={(projectId) => {
              loadProjects();
              router.push(`/projects/${projectId}`);
            }}
          />
        </CardContent>
      </Card>

      {projects && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <StatTile icon={FolderOpen} value={projects.length} label="Projects" />
          <StatTile icon={Clapperboard} value={totals.shorts} label="Shorts generated" />
          <StatTile icon={Megaphone} value={totals.posts} label="Platform posts" />
        </div>
      )}

      <section className="space-y-4">
        <h2 className="text-sm font-medium text-muted-foreground">
          Recent Projects
        </h2>

        {projects === null && !error && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-xl" />
            ))}
          </div>
        )}

        {projects !== null && projects.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-14 text-center">
            <FolderOpen className="size-6 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">No projects yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Upload your first video above — RECAST will handle transcription,
              analysis, clipping and the full campaign.
            </p>
          </div>
        )}

        {projects && projects.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
