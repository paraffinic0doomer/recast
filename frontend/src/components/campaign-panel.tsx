"use client";

import { useCallback, useState } from "react";
import {
  Play,
  Camera,
  Music2,
  Users,
  Briefcase,
  MessageCircle,
  Copy,
  Check,
  RotateCw,
  Megaphone,
  Sparkles,
  Loader2,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { SectionHeader, EmptyState, FieldLabel } from "@/components/workspace";
import { AiEngineNotice } from "@/components/ai-engine-notice";
import { ScoreRing } from "@/components/score-ring";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { Campaign, PlatformKey } from "@/types/project";

/** Real platform limits, used for the character counters. */
const LIMITS: Record<string, number> = {
  youtube_title: 100,
  youtube_description: 5000,
  instagram_caption: 2200,
  instagram_cover: 60,
  tiktok_caption: 2200,
  facebook_caption: 63206,
  linkedin_post: 3000,
  x_post: 280,
};

const PLATFORMS: {
  key: PlatformKey;
  label: string;
  icon: React.ElementType;
  /** How this platform's voice differs — shown so the tabs aren't interchangeable. */
  angle: string;
}[] = [
  // lucide dropped brand marks, so these are semantic stand-ins.
  { key: "youtube", label: "YouTube", icon: Play, angle: "Search-led title, chapters and SEO" },
  { key: "instagram", label: "Instagram", icon: Camera, angle: "Visual-first caption with a cover line" },
  { key: "tiktok", label: "TikTok", icon: Music2, angle: "Spoken hook for the first three seconds" },
  { key: "facebook", label: "Facebook", icon: Users, angle: "Conversational, built for sharing" },
  { key: "linkedin", label: "LinkedIn", icon: Briefcase, angle: "Professional insight and takeaways" },
  { key: "x", label: "X", icon: MessageCircle, angle: "Tight post plus a follow-up thread" },
];

function formatTimecode(seconds: number) {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
}

function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      toast.error("Couldn't copy", { description: "Clipboard access was blocked." });
    }
  }, [value]);

  return (
    <Button size="sm" variant="ghost" onClick={copy} disabled={!value}>
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {copied ? "Copied" : label}
    </Button>
  );
}

function CharCount({ value, limit }: { value: string; limit?: number }) {
  const n = value.length;
  const over = limit != null && n > limit;
  const near = limit != null && !over && n > limit * 0.9;
  return (
    <span
      className={cn(
        "font-mono text-xs tabular-nums",
        over ? "text-destructive" : near ? "text-warning" : "text-muted-foreground",
      )}
    >
      {n}
      {limit != null && `/${limit}`}
    </span>
  );
}

/** A labelled block of generated copy with its own copy button and counter. */
function Field({
  label,
  value,
  limit,
}: {
  label: string;
  value: string;
  limit?: number;
}) {
  if (!value) return null;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <FieldLabel>{label}</FieldLabel>
        <div className="flex items-center gap-2">
          <CharCount value={value} limit={limit} />
          <CopyButton value={value} />
        </div>
      </div>
      <p className="whitespace-pre-wrap rounded-xl border border-border bg-surface px-4 py-3.5 text-sm leading-relaxed text-foreground">
        {value}
      </p>
    </div>
  );
}

function TagRow({
  label,
  items,
  copyValue,
}: {
  label: string;
  items: string[];
  copyValue?: string;
}) {
  if (!items.length) return null;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <FieldLabel>
          {label} ({items.length})
        </FieldLabel>
        <CopyButton value={copyValue ?? items.join(" ")} label="Copy all" />
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <span
            key={item}
            className="max-w-full break-words rounded-lg border border-border bg-surface px-2.5 py-1 text-sm text-foreground"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

interface CampaignPanelProps {
  campaign: Campaign | null;
  campaignScore: number | null;
  isGenerating: boolean;
  generatingPlatform: PlatformKey | null;
  onGenerate: (platform?: PlatformKey) => void;
}

export function CampaignPanel({
  campaign,
  campaignScore,
  isGenerating,
  generatingPlatform,
  onGenerate,
}: CampaignPanelProps) {
  const generatedCount = campaign
    ? PLATFORMS.filter((p) => campaign[p.key] != null).length
    : 0;

  return (
    <section className="space-y-6">
      <SectionHeader
        title="Campaign"
        description={
          generatedCount > 0
            ? `${generatedCount} of ${PLATFORMS.length} platforms written — each one from scratch, not a rewrite of the same post.`
            : "Native copy for all six platforms, written from your Content DNA."
        }
        action={
          <div className="flex items-center gap-4">
            {campaignScore != null && (
              <ScoreRing value={campaignScore} size={56} label="Coverage" />
            )}
            <Button onClick={() => onGenerate()} disabled={isGenerating}>
              {isGenerating && !generatingPlatform ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {isGenerating && !generatingPlatform
                ? "Generating…"
                : campaign
                  ? "Regenerate all"
                  : "Generate campaign"}
            </Button>
          </div>
        }
      />

      <AiEngineNotice />

      {!campaign ? (
        <EmptyState
          icon={Megaphone}
          tone="pending"
          title="No campaign generated yet"
          description="One click writes a native post for YouTube, Instagram, TikTok, Facebook, LinkedIn and X — each with its own tone, length and hook."
          action={
            <Button size="lg" onClick={() => onGenerate()} disabled={isGenerating}>
              {isGenerating ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {isGenerating ? "Generating…" : "Generate campaign"}
            </Button>
          }
        />
      ) : (
        <Tabs defaultValue="youtube">
          <TabsList className="flex w-full flex-wrap">
            {PLATFORMS.map(({ key, label, icon: Icon }) => (
              <TabsTrigger key={key} value={key} className="gap-1.5">
                <Icon className="size-3.5" />
                {label}
                {campaign[key] == null && (
                  <span className="size-1.5 rounded-full bg-muted-foreground/40" />
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          {PLATFORMS.map(({ key, label, icon: Icon, angle }) => {
            const content = campaign[key];
            const busy = generatingPlatform === key;

            return (
              <TabsContent key={key} value={key} className="mt-6 space-y-6">
                {/* Platform header — states the angle so the tabs read as
                    six different strategies rather than six copies. */}
                <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 rounded-2xl border border-border bg-card px-5 py-4">
                  <div className="flex min-w-[14rem] flex-1 items-center gap-3.5">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Icon className="size-4.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-[0.95rem] font-semibold text-foreground">
                        {label}
                      </p>
                      <p className="mt-0.5 text-sm text-muted-foreground">{angle}</p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => onGenerate(key)}
                    disabled={isGenerating}
                  >
                    <RotateCw className={cn("size-4", busy && "animate-spin")} />
                    {busy ? "Regenerating…" : "Regenerate"}
                  </Button>
                </div>

                {!content ? (
                  <EmptyState
                    icon={Icon}
                    tone="pending"
                    title={`Nothing written for ${label} yet`}
                    description={`Write ${label} on its own — the other platforms stay exactly as they are.`}
                    action={
                      <Button
                        size="lg"
                        onClick={() => onGenerate(key)}
                        disabled={isGenerating}
                      >
                        {busy ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Sparkles className="size-4" />
                        )}
                        {busy ? "Writing…" : `Generate ${label} post`}
                      </Button>
                    }
                  />
                ) : (
                  <>
                    {key === "youtube" && campaign.youtube && (
                      <>
                        <div className="space-y-2">
                          <FieldLabel>Title options</FieldLabel>
                          <div className="space-y-2">
                            {campaign.youtube.titles.map((title, i) => (
                              <div
                                key={i}
                                className="flex items-start justify-between gap-4 rounded-xl border border-border bg-surface px-4 py-3"
                              >
                                <p className="text-[0.95rem] font-medium leading-snug text-foreground">
                                  {title}
                                </p>
                                <div className="flex shrink-0 items-center gap-2">
                                  <CharCount value={title} limit={LIMITS.youtube_title} />
                                  <CopyButton value={title} label="" />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        <Field
                          label="Description"
                          value={campaign.youtube.description}
                          limit={LIMITS.youtube_description}
                        />

                        {campaign.youtube.chapters.length > 0 && (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between gap-2">
                              <FieldLabel>Chapters</FieldLabel>
                              <CopyButton
                                value={campaign.youtube.chapters
                                  .map((c) => `${formatTimecode(c.timestamp)} ${c.label}`)
                                  .join("\n")}
                                label="Copy all"
                              />
                            </div>
                            <div className="rounded-xl border border-border bg-surface px-4 py-3">
                              {campaign.youtube.chapters.map((c, i) => (
                                <div key={i} className="flex gap-4 py-1 text-sm">
                                  <span className="font-mono tabular-nums text-primary">
                                    {formatTimecode(c.timestamp)}
                                  </span>
                                  <span className="text-foreground">{c.label}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                          <TagRow
                            label="SEO keywords"
                            items={campaign.youtube.seo_keywords}
                            copyValue={campaign.youtube.seo_keywords.join(", ")}
                          />
                          <TagRow
                            label="Tags"
                            items={campaign.youtube.tags}
                            copyValue={campaign.youtube.tags.join(", ")}
                          />
                        </div>
                      </>
                    )}

                    {key === "instagram" && campaign.instagram && (
                      <>
                        <Field
                          label="Reel cover text"
                          value={campaign.instagram.reel_cover_text}
                          limit={LIMITS.instagram_cover}
                        />
                        <Field
                          label="Caption"
                          value={campaign.instagram.caption}
                          limit={LIMITS.instagram_caption}
                        />
                        <Field label="Call to action" value={campaign.instagram.cta} />
                        <TagRow label="Hashtags" items={campaign.instagram.hashtags} />
                      </>
                    )}

                    {key === "tiktok" && campaign.tiktok && (
                      <>
                        <Field label="Spoken hook" value={campaign.tiktok.hook} />
                        <Field
                          label="Caption"
                          value={campaign.tiktok.caption}
                          limit={LIMITS.tiktok_caption}
                        />
                        <Field label="Call to action" value={campaign.tiktok.cta} />
                        <TagRow label="Hashtags" items={campaign.tiktok.hashtags} />
                      </>
                    )}

                    {key === "facebook" && campaign.facebook && (
                      <>
                        <Field
                          label="Caption"
                          value={campaign.facebook.caption}
                          limit={LIMITS.facebook_caption}
                        />
                        <Field label="Call to action" value={campaign.facebook.cta} />
                        <TagRow label="Hashtags" items={campaign.facebook.hashtags} />
                      </>
                    )}

                    {key === "linkedin" && campaign.linkedin && (
                      <>
                        <Field
                          label="Post"
                          value={campaign.linkedin.post}
                          limit={LIMITS.linkedin_post}
                        />
                        <Field label="Call to action" value={campaign.linkedin.cta} />
                        <TagRow label="Hashtags" items={campaign.linkedin.hashtags} />
                      </>
                    )}

                    {key === "x" && campaign.x && (
                      <>
                        <Field label="Post" value={campaign.x.post} limit={LIMITS.x_post} />
                        {campaign.x.thread.length > 0 && (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between gap-2">
                              <FieldLabel>
                                Thread ({campaign.x.thread.length} posts)
                              </FieldLabel>
                              <CopyButton
                                value={campaign.x.thread.join("\n\n")}
                                label="Copy all"
                              />
                            </div>
                            <div className="space-y-2">
                              {campaign.x.thread.map((post, i) => (
                                <div
                                  key={i}
                                  className="rounded-xl border border-border bg-surface px-4 py-3.5"
                                >
                                  <div className="mb-2 flex items-center justify-between">
                                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                                      {i + 2}/{campaign.x!.thread.length + 1}
                                    </span>
                                    <div className="flex items-center gap-2">
                                      <CharCount value={post} limit={LIMITS.x_post} />
                                      <CopyButton value={post} label="" />
                                    </div>
                                  </div>
                                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                                    {post}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </section>
  );
}
