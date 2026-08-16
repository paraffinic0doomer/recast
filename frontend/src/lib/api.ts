import type {
  BestMomentsResponse,
  CampaignResponse,
  PlatformKey,
  EvaluationResponse,
  ThumbnailsResponse,
  Clip,
  ClipsResponse,
  ContentDNAResponse,
  HealthResponse,
  ProjectDetail,
  ProjectSummary,
  TranscriptResponse,
} from "@/types/project";

import { getAccessKey, clearAccessKey } from "@/lib/access";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Absolute URL for a stored media file.
 *
 * The key travels as a query parameter here, not a header: <video src> and
 * <img src> are fetched by the browser itself and cannot carry custom headers.
 */
export function mediaUrl(path: string): string {
  const key = getAccessKey();
  if (!key) return `${API_URL}${path}`;
  const sep = path.includes("?") ? "&" : "?";
  return `${API_URL}${path}${sep}k=${encodeURIComponent(key)}`;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Sent on every request so a tunnelled backend answers with JSON.
 *
 * When the API is exposed through localtunnel — the usual setup when the
 * frontend is hosted but the pipeline runs on a local machine, because FFmpeg
 * needs real CPU and large uploads exceed most proxies' body limits — the
 * service returns an HTML interstitial to anything that looks like a browser.
 * This header opts out of it. Every other host ignores an unknown header, so
 * it costs nothing when the API is hosted normally.
 */
const TUNNEL_HEADERS = { "bypass-tunnel-reminder": "true" };

function withHeaders(init?: RequestInit): RequestInit {
  const key = getAccessKey();
  return {
    ...init,
    headers: {
      ...TUNNEL_HEADERS,
      ...(key ? { "X-Access-Key": key } : {}),
      ...(init?.headers ?? {}),
    },
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api${path}`, withHeaders(init));
  if (!res.ok) {
    // A rejected key is stale or wrong; drop it so the gate reappears rather
    // than leaving every subsequent request failing silently.
    if (res.status === 401) clearAccessKey();
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? res.statusText, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  listProjects: () => request<ProjectSummary[]>("/projects"),

  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),

  createProject: (title?: string) =>
    request<ProjectSummary>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title ?? null }),
    }),

  uploadVideo: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append("project_id", projectId);
    formData.append("video", file);
    return request<ProjectSummary>("/upload", {
      method: "POST",
      body: formData,
    });
  },

  getTranscript: (id: string) =>
    request<TranscriptResponse>(`/projects/${id}/transcript`),

  processProject: (id: string) =>
    request<ProjectSummary>(`/projects/${id}/process`, { method: "POST" }),

  analyzeProject: (id: string) =>
    request<ProjectSummary>(`/projects/${id}/analyze`, { method: "POST" }),

  getContentDna: (id: string) =>
    request<ContentDNAResponse>(`/projects/${id}/content-dna`),

  detectMoments: (id: string) =>
    request<ProjectSummary>(`/projects/${id}/moments`, { method: "POST" }),

  getMoments: (id: string) =>
    request<BestMomentsResponse>(`/projects/${id}/moments`),

  createClip: (id: string, momentId: string) =>
    request<Clip>(`/projects/${id}/clips`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ moment_id: momentId }),
    }),

  getClips: (id: string) => request<ClipsResponse>(`/projects/${id}/clips`),

  generateCampaign: (id: string, platform?: PlatformKey) =>
    request<ProjectSummary>(
      `/projects/${id}/campaign${platform ? `?platform=${platform}` : ""}`,
      { method: "POST" },
    ),

  getCampaign: (id: string) => request<CampaignResponse>(`/projects/${id}/campaign`),

  generateThumbnails: (id: string) =>
    request<ProjectSummary>(`/projects/${id}/thumbnails`, { method: "POST" }),

  getThumbnails: (id: string) =>
    request<ThumbnailsResponse>(`/projects/${id}/thumbnails`),

  evaluateCampaign: (id: string) =>
    request<ProjectSummary>(`/projects/${id}/evaluate`, { method: "POST" }),

  getEvaluation: (id: string) =>
    request<EvaluationResponse>(`/projects/${id}/evaluation`),

  /** Direct URL that serves the clip as a file attachment. */
  clipDownloadUrl: (id: string, clipId: string) =>
    mediaUrl(`/api/projects/${id}/clips/${clipId}/download`),

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),
};
