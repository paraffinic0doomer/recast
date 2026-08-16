"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProjectSummary } from "@/types/project";

export const API_ERROR =
  "Can't reach the RECAST API. Make sure the backend is running on the configured NEXT_PUBLIC_API_URL.";

/**
 * The project list, shared by every workspace route.
 *
 * `projects === null` means "still loading" and is deliberately distinct from
 * an empty array, so each page can tell a skeleton apart from an empty state.
 */
export function useProjects() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listProjects()
      .then((data) => {
        if (cancelled) return;
        setProjects(data);
        setError(null);
      })
      .catch(() => {
        if (!cancelled) setError(API_ERROR);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { projects, error };
}
