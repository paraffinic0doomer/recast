export type ProjectStatus =
  | "pending"
  | "uploaded"
  | "processing"
  | "transcribing"
  | "transcribed"
  | "analyzing"
  | "analyzed"
  | "detecting_moments"
  | "moments_ready"
  | "generating"
  | "completed"
  | "failed";

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  text: string;
  language: string | null;
  duration: number | null;
  segments: TranscriptSegment[];
}

export interface TranscriptResponse extends Transcript {
  project_id: string;
}

export interface KeyMoment {
  timestamp: number | null;
  title: string;
  description: string;
}

/**
 * The single source of truth for all downstream generated content.
 * Platform generators consume ContentDNA + transcript — they never
 * re-derive their own understanding of the video.
 */
export interface ContentDNA {
  primary_topic: string;
  secondary_topics: string[];
  audience: string;
  tone: string;
  content_type: string;
  core_message: string;
  key_points: string[];
  important_concepts: string[];
  entities: string[];
  keywords: string[];
  hooks: string[];
  cta: string | null;
  key_moments: KeyMoment[];
}

export interface MomentScores {
  hook_strength: number;
  information_value: number;
  standalone_quality: number;
  emotional_interest: number;
}

export interface BestMoment {
  id: string;
  start: number;
  end: number;
  title: string;
  hook: string;
  reason: string;
  score: number;
  scores: MomentScores;
}

export interface BestMomentsResponse {
  project_id: string;
  moments: BestMoment[];
}

export interface Clip {
  clip_id: string;
  moment_id: string;
  video_url: string;
  thumbnail_url: string;
  title: string;
  hook: string;
  score: number;
  start: number;
  end: number;
  duration: number;
  width: number;
  height: number;
  vertical: boolean;
  subtitled: boolean;
}

export interface ClipsResponse {
  project_id: string;
  clips: Clip[];
}

export interface Chapter {
  timestamp: number;
  label: string;
}

export interface YouTubeContent {
  titles: string[];
  description: string;
  chapters: Chapter[];
  seo_keywords: string[];
  tags: string[];
}

export interface InstagramContent {
  caption: string;
  hashtags: string[];
  cta: string;
  reel_cover_text: string;
}

export interface TikTokContent {
  hook: string;
  caption: string;
  hashtags: string[];
  cta: string;
}

export interface FacebookContent {
  caption: string;
  cta: string;
  hashtags: string[];
}

export interface LinkedInContent {
  post: string;
  cta: string;
  hashtags: string[];
}

export interface XContent {
  post: string;
  thread: string[];
}

export type PlatformKey =
  | "youtube"
  | "instagram"
  | "tiktok"
  | "facebook"
  | "linkedin"
  | "x";

export interface Campaign {
  youtube: YouTubeContent | null;
  instagram: InstagramContent | null;
  tiktok: TikTokContent | null;
  facebook: FacebookContent | null;
  linkedin: LinkedInContent | null;
  x: XContent | null;
}

export interface CampaignResponse {
  project_id: string;
  campaign: Campaign;
  campaign_score: number | null;
}

export interface ThumbnailConcept {
  id: string;
  headline: string;
  visual_concept: string;
  subject_placement: string;
  emotional_angle: string;
  why_it_works: string;
  recommended_use_case: string;
  text_position: string;
  accent_color: string;
  timestamp: number | null;
  frame_url: string | null;
}

export interface ThumbnailsResponse {
  project_id: string;
  concepts: ThumbnailConcept[];
  image_generation_available: boolean;
}

export interface Improvement {
  area: string;
  suggestion: string;
  priority: "high" | "medium" | "low";
}

export interface CampaignEvaluation {
  overall: number;
  content_quality: number;
  platform_adaptation: number;
  hook_strength: number;
  source_consistency: number;
  seo: number;
  cta: number;
  summary: string;
  improvements: Improvement[];
}

export interface EvaluationResponse {
  project_id: string;
  evaluation: CampaignEvaluation | null;
  completeness_score: number | null;
}

export interface ContentDNAResponse {
  project_id: string;
  content_dna: ContentDNA;
}

export interface ProjectSummary {
  id: string;
  title: string;
  status: ProjectStatus;
  error_message: string | null;
  video_filename: string | null;
  video_url: string | null;
  duration_seconds: number | null;
  video_width: number | null;
  video_height: number | null;
  video_fps: number | null;
  video_size_bytes: number | null;
  campaign_score: number | null;
  clip_count: number;
  post_count: number;
  moment_count: number;
  has_content_dna: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  transcript: Transcript | null;
  content_dna: ContentDNA | null;
  key_topics: unknown;
  best_moments: BestMoment[] | null;
  clips: Clip[] | null;
  platform_content: Campaign | null;
  thumbnail_concepts: ThumbnailConcept[] | null;
  campaign_evaluation: CampaignEvaluation | null;
}

/** Real capacity of the rotating Groq key pool. */
export interface AiEngineInfo {
  keys_total: number;
  keys_available: number;
  rate_limited: boolean;
  retry_after_seconds: number | null;
}

export interface HealthResponse {
  status: string;
  openai_configured: boolean;
  ai?: AiEngineInfo;
}
