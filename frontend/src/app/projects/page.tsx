"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { WifiOff, FolderOpen, Search, Plus, SearchX } from "lucide-react";
import { ProjectCard } from "@/components/project-card";
import { Page, PageHeader, EmptyState } from "@/components/workspace";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useProjects } from "@/lib/use-projects";
import { cn } from "@/lib/utils";

type Filter = "all" | "ready" | "working" | "attention";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "ready", label: "Campaign ready" },
  { key: "working", label: "In progress" },
  { key: "attention", label: "Needs attention" },
];

export default function ProjectsPage() {
  const { projects, error } = useProjects();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (projects ?? []).filter((p) => {
      const matchesTerm =
        !term ||
        p.title.toLowerCase().includes(term) ||
        (p.video_filename ?? "").toLowerCase().includes(term);

      const matchesFilter =
        filter === "all" ||
        (filter === "ready" && p.status === "completed") ||
        (filter === "attention" && p.status === "failed") ||
        (filter === "working" &&
          p.status !== "completed" &&
          p.status !== "failed");

      return matchesTerm && matchesFilter;
    });
  }, [projects, query, filter]);

  return (
    <Page className="space-y-8">
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Every video you've brought into RECAST, and how far each one has travelled through the pipeline."
        action={
          <Button asChild>
            <Link href="/">
              <Plus className="size-4" />
              New project
            </Link>
          </Button>
        }
      />

      {error && (
        <Alert variant="destructive">
          <WifiOff className="size-4" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {projects && projects.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[16rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search projects…"
              aria-label="Search projects"
              className="h-9 pl-9"
            />
          </div>
          <div className="flex flex-wrap items-center gap-1 rounded-xl border border-border bg-surface p-1">
            {FILTERS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                aria-pressed={filter === key}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm transition-colors",
                  filter === key
                    ? "bg-secondary font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {projects === null && !error && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-2xl" />
          ))}
        </div>
      )}

      {projects !== null && projects.length === 0 && (
        <EmptyState
          icon={FolderOpen}
          title="No projects yet"
          description="Head to the Studio and upload a video to create your first campaign."
          action={
            <Button asChild>
              <Link href="/">Go to Studio</Link>
            </Button>
          }
        />
      )}

      {projects !== null && projects.length > 0 && visible.length === 0 && (
        <EmptyState
          icon={SearchX}
          title="Nothing matches"
          description="Try a different search term, or clear the filter to see everything."
          action={
            <Button
              variant="outline"
              onClick={() => {
                setQuery("");
                setFilter("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      )}

      {visible.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </Page>
  );
}
