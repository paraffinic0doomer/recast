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

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function mediaUrl(path: string): string {
  return `${API_URL}${path}`;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api${path}`, init);
  if (!res.ok) {
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
    `${API_URL}/api/projects/${id}/clips/${clipId}/download`,

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),
};
