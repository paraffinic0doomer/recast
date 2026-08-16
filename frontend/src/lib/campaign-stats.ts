import type { Campaign, ProjectDetail } from "@/types/project";

export interface CampaignStats {
  shorts: number;
  platforms: number;
  thumbnails: number;
  moments: number;
  /** Every discrete deliverable produced, counted individually. */
  assets: number;
}

/**
 * Counts real generated deliverables — nothing is inflated. Each item counted
 * is something the user can actually copy, download or publish.
 */
export function countCampaignStats(project: ProjectDetail): CampaignStats {
  const campaign = project.platform_content;
  const shorts = project.clips?.length ?? 0;
  const thumbnails = project.thumbnail_concepts?.length ?? 0;
  const moments = project.best_moments?.length ?? 0;

  let assets = 0;
  let platforms = 0;

  if (campaign) {
    const yt = campaign.youtube;
    if (yt) {
      platforms += 1;
      assets += yt.titles.length;
      if (yt.description) assets += 1;
      if (yt.chapters.length) assets += 1;
      if (yt.seo_keywords.length) assets += 1;
      if (yt.tags.length) assets += 1;
    }

    const ig = campaign.instagram;
    if (ig) {
      platforms += 1;
      if (ig.caption) assets += 1;
      if (ig.hashtags.length) assets += 1;
      if (ig.cta) assets += 1;
      if (ig.reel_cover_text) assets += 1;
    }

    const tt = campaign.tiktok;
    if (tt) {
      platforms += 1;
      if (tt.hook) assets += 1;
      if (tt.caption) assets += 1;
      if (tt.hashtags.length) assets += 1;
      if (tt.cta) assets += 1;
    }

    const fb = campaign.facebook;
    if (fb) {
      platforms += 1;
      if (fb.caption) assets += 1;
      if (fb.cta) assets += 1;
      if (fb.hashtags.length) assets += 1;
    }

    const li = campaign.linkedin;
    if (li) {
      platforms += 1;
      if (li.post) assets += 1;
      if (li.cta) assets += 1;
      if (li.hashtags.length) assets += 1;
    }

    const x = campaign.x;
    if (x) {
      platforms += 1;
      if (x.post) assets += 1;
      if (x.thread.length) assets += 1;
    }
  }

  assets += shorts + thumbnails;

  return { shorts, platforms, thumbnails, moments, assets };
}

const PLATFORM_ORDER: { key: keyof Campaign; label: string }[] = [
  { key: "youtube", label: "YouTube" },
  { key: "instagram", label: "Instagram" },
  { key: "tiktok", label: "TikTok" },
  { key: "facebook", label: "Facebook" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "x", label: "X" },
];

/** Plain-text export of the whole campaign, ready to paste or save. */
export function buildCampaignExport(project: ProjectDetail): string {
  const lines: string[] = [];
  const push = (s = "") => lines.push(s);

  push(`RECAST CAMPAIGN — ${project.title}`);
  push("=".repeat(60));
  push(`Source video: ${project.video_filename ?? "n/a"}`);
  if (project.duration_seconds) {
    push(`Duration: ${Math.round(project.duration_seconds)}s`);
  }
  if (project.campaign_evaluation) {
    push(`Quality score: ${project.campaign_evaluation.overall}/100`);
  }
  if (project.campaign_score != null) {
    push(`Completeness score: ${project.campaign_score}/100`);
  }
  push();

  const dna = project.content_dna;
  if (dna) {
    push("CONTENT DNA");
    push("-".repeat(60));
    push(`Primary topic: ${dna.primary_topic}`);
    push(`Audience: ${dna.audience}`);
    push(`Tone: ${dna.tone}`);
    push(`Content type: ${dna.content_type}`);
    push(`Core message: ${dna.core_message}`);
    if (dna.keywords.length) push(`Keywords: ${dna.keywords.join(", ")}`);
    if (dna.cta) push(`CTA: ${dna.cta}`);
    push();
  }

  const campaign = project.platform_content;
  if (campaign) {
    for (const { key, label } of PLATFORM_ORDER) {
      const content = campaign[key];
      if (!content) continue;
      push(label.toUpperCase());
      push("-".repeat(60));

      if (key === "youtube" && campaign.youtube) {
        campaign.youtube.titles.forEach((t, i) => push(`Title ${i + 1}: ${t}`));
        push();
        push("Description:");
        push(campaign.youtube.description);
        if (campaign.youtube.chapters.length) {
          push();
          push("Chapters:");
          campaign.youtube.chapters.forEach((c) => {
            const m = Math.floor(c.timestamp / 60);
            const s = String(Math.floor(c.timestamp % 60)).padStart(2, "0");
            push(`  ${m}:${s} ${c.label}`);
          });
        }
        if (campaign.youtube.seo_keywords.length) {
          push();
          push(`SEO keywords: ${campaign.youtube.seo_keywords.join(", ")}`);
        }
        if (campaign.youtube.tags.length) {
          push(`Tags: ${campaign.youtube.tags.join(", ")}`);
        }
      }

      if (key === "instagram" && campaign.instagram) {
        push(`Reel cover: ${campaign.instagram.reel_cover_text}`);
        push();
        push(campaign.instagram.caption);
        push();
        push(`CTA: ${campaign.instagram.cta}`);
        push(`Hashtags: ${campaign.instagram.hashtags.join(" ")}`);
      }

      if (key === "tiktok" && campaign.tiktok) {
        push(`Hook: ${campaign.tiktok.hook}`);
        push();
        push(campaign.tiktok.caption);
        push();
        push(`CTA: ${campaign.tiktok.cta}`);
        push(`Hashtags: ${campaign.tiktok.hashtags.join(" ")}`);
      }

      if (key === "facebook" && campaign.facebook) {
        push(campaign.facebook.caption);
        push();
        push(`CTA: ${campaign.facebook.cta}`);
        push(`Hashtags: ${campaign.facebook.hashtags.join(" ")}`);
      }

      if (key === "linkedin" && campaign.linkedin) {
        push(campaign.linkedin.post);
        push();
        push(`CTA: ${campaign.linkedin.cta}`);
        push(`Hashtags: ${campaign.linkedin.hashtags.join(" ")}`);
      }

      if (key === "x" && campaign.x) {
        push(campaign.x.post);
        if (campaign.x.thread.length) {
          push();
          push("Thread:");
          campaign.x.thread.forEach((t, i) => push(`  ${i + 2}. ${t}`));
        }
      }

      push();
    }
  }

  if (project.thumbnail_concepts?.length) {
    push("THUMBNAIL CONCEPTS");
    push("-".repeat(60));
    project.thumbnail_concepts.forEach((c, i) => {
      push(`${i + 1}. ${c.headline}`);
      push(`   Visual: ${c.visual_concept}`);
      push(`   Use: ${c.recommended_use_case}`);
    });
    push();
  }

  if (project.clips?.length) {
    push("SHORTS");
    push("-".repeat(60));
    project.clips.forEach((c, i) => {
      push(`${i + 1}. ${c.title} (${Math.round(c.duration)}s, ${c.width}x${c.height})`);
    });
    push();
  }

  if (project.campaign_evaluation?.improvements.length) {
    push("SUGGESTED IMPROVEMENTS");
    push("-".repeat(60));
    project.campaign_evaluation.improvements.forEach((imp, i) => {
      push(`${i + 1}. [${imp.priority.toUpperCase()}] ${imp.area}: ${imp.suggestion}`);
    });
    push();
  }

  push("Generated by RECAST — one piece of content, an entire campaign.");
  return lines.join("\n");
}

/** Triggers a client-side download without touching the server. */
export function downloadText(filename: string, contents: string): void {
  const blob = new Blob([contents], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
