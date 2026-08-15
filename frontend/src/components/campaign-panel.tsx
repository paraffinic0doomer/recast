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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
  accent: string;
}[] = [
  // lucide dropped brand marks, so these are semantic stand-ins.
  { key: "youtube", label: "YouTube", icon: Play, accent: "text-red-600 dark:text-red-400" },
  { key: "instagram", label: "Instagram", icon: Camera, accent: "text-pink-600 dark:text-pink-400" },
  { key: "tiktok", label: "TikTok", icon: Music2, accent: "text-foreground" },
  { key: "facebook", label: "Facebook", icon: Users, accent: "text-blue-600 dark:text-blue-400" },
  { key: "linkedin", label: "LinkedIn", icon: Briefcase, accent: "text-sky-700 dark:text-sky-400" },
  { key: "x", label: "X", icon: MessageCircle, accent: "text-foreground" },
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
        "text-xs tabular-nums",
        over ? "font-medium text-red-600 dark:text-red-400" : near ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground",
      )}
    >
      {n}
      {limit != null && ` / ${limit}`}
    </span>
  );
}

/** A labelled block of generated copy with its own copy button and counter. */
function Field({
  label,
  value,
  limit,
  mono = false,
}: {
  label: string;
  value: string;
  limit?: number;
  mono?: boolean;
}) {
  if (!value) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <div className="flex items-center gap-2">
          <CharCount value={value} limit={limit} />
          <CopyButton value={value} />
        </div>
      </div>
      <p
        className={cn(
          "whitespace-pre-wrap rounded-lg border bg-muted/30 px-4 py-3 text-sm leading-relaxed text-foreground",
          mono && "font-mono text-xs",
        )}
      >
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
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
          <span className="ml-1.5 font-normal normal-case tracking-normal">
            ({items.length})
          </span>
        </span>
        <CopyButton value={copyValue ?? items.join(" ")} label="Copy all" />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <Badge key={item} variant="secondary" className="font-normal">
            {item}
          </Badge>
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
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Megaphone className="size-4" />
            Campaign
            {generatedCount > 0 && (
              <span className="text-xs font-normal text-muted-foreground">
                {generatedCount} of {PLATFORMS.length} platforms
              </span>
            )}
          </CardTitle>
          <div className="flex items-center gap-3">
            {campaignScore != null && (
              <div className="text-right">
                <div className="text-xl font-semibold leading-none tabular-nums text-foreground">
                  {campaignScore}
                  <span className="text-xs font-normal text-muted-foreground">
                    /100
                  </span>
                </div>
                <p className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                  Campaign score
                </p>
              </div>
            )}
            <Button
              size="sm"
              onClick={() => onGenerate()}
              disabled={isGenerating}
            >
              {isGenerating && !generatingPlatform ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Sparkles className="size-3.5" />
              )}
              {isGenerating && !generatingPlatform
                ? "Generating…"
                : campaign
                  ? "Regenerate All"
                  : "Generate Campaign"}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {!campaign ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed py-14 text-center">
            <Megaphone className="size-6 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">
                No campaign generated yet
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Generate platform-native copy for all six platforms from your
                Content DNA.
              </p>
            </div>
          </div>
        ) : (
          <Tabs defaultValue="youtube">
            <TabsList className="mb-5 flex w-full flex-wrap">
              {PLATFORMS.map(({ key, label, icon: Icon, accent }) => (
                <TabsTrigger key={key} value={key} className="gap-1.5">
                  <Icon className={cn("size-3.5", accent)} />
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>

            {PLATFORMS.map(({ key, label }) => {
              const content = campaign[key];
              const busy = generatingPlatform === key;

              return (
                <TabsContent key={key} value={key} className="space-y-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-muted-foreground">
                      {content
                        ? `Written natively for ${label}`
                        : `${label} content was not generated`}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onGenerate(key)}
                      disabled={isGenerating}
                    >
                      <RotateCw
                        className={cn("size-3.5", busy && "animate-spin")}
                      />
                      {busy ? "Regenerating…" : "Regenerate"}
                    </Button>
                  </div>

                  {!content ? (
                    <div className="rounded-xl border border-dashed py-10 text-center text-sm text-muted-foreground">
                      Nothing generated for {label} yet.
                    </div>
                  ) : (
                    <>
                      {key === "youtube" && campaign.youtube && (
                        <>
                          <div className="space-y-1.5">
                            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                              Title options
                            </span>
                            <div className="space-y-2">
                              {campaign.youtube.titles.map((title, i) => (
                                <div
                                  key={i}
                                  className="flex items-start justify-between gap-3 rounded-lg border bg-muted/30 px-4 py-2.5"
                                >
                                  <p className="text-sm font-medium leading-snug text-foreground">
                                    {title}
                                  </p>
                                  <div className="flex shrink-0 items-center gap-2">
                                    <CharCount
                                      value={title}
                                      limit={LIMITS.youtube_title}
                                    />
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
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Chapters
                                </span>
                                <CopyButton
                                  value={campaign.youtube.chapters
                                    .map(
                                      (c) =>
                                        `${formatTimecode(c.timestamp)} ${c.label}`,
                                    )
                                    .join("\n")}
                                  label="Copy all"
                                />
                              </div>
                              <div className="rounded-lg border bg-muted/30 px-4 py-3 font-mono text-xs">
                                {campaign.youtube.chapters.map((c, i) => (
                                  <div key={i} className="flex gap-3 py-0.5">
                                    <span className="tabular-nums text-primary">
                                      {formatTimecode(c.timestamp)}
                                    </span>
                                    <span className="text-foreground">
                                      {c.label}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
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
                          <Field
                            label="Post"
                            value={campaign.x.post}
                            limit={LIMITS.x_post}
                          />
                          {campaign.x.thread.length > 0 && (
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Thread
                                  <span className="ml-1.5 font-normal normal-case tracking-normal">
                                    ({campaign.x.thread.length} posts)
                                  </span>
                                </span>
                                <CopyButton
                                  value={campaign.x.thread.join("\n\n")}
                                  label="Copy all"
                                />
                              </div>
                              <div className="space-y-2">
                                {campaign.x.thread.map((post, i) => (
                                  <div
                                    key={i}
                                    className="rounded-lg border bg-muted/30 px-4 py-3"
                                  >
                                    <div className="mb-1.5 flex items-center justify-between">
                                      <span className="text-xs font-medium text-muted-foreground">
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

                      <Separator />
                      <p className="text-xs text-muted-foreground">
                        Generated from this video&apos;s Content DNA — written
                        specifically for {label}, not reused across platforms.
                      </p>
                    </>
                  )}
                </TabsContent>
              );
            })}
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
