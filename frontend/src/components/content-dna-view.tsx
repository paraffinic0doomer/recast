"use client";

import {
  Dna,
  Users,
  Palette,
  Film,
  Quote,
  Tag,
  Sparkles,
  Megaphone,
  Lightbulb,
  ListChecks,
  AtSign,
  Clock,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ContentDNA } from "@/types/project";

function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Top-row summary tile: one high-signal attribute of the content. */
function AttributeTile({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "flex size-7 items-center justify-center rounded-lg",
            accent,
          )}
        >
          <Icon className="size-3.5" />
        </div>
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      </div>
      <p className="mt-2.5 text-sm font-medium leading-snug text-foreground">
        {value || <span className="text-muted-foreground">Not identified</span>}
      </p>
    </div>
  );
}

function ChipSection({
  icon: Icon,
  title,
  items,
  variant = "secondary",
  emptyHint,
}: {
  icon: React.ElementType;
  title: string;
  items: string[];
  variant?: "secondary" | "outline";
  emptyHint?: string;
}) {
  if (items.length === 0 && !emptyHint) return null;
  return (
    <div className="space-y-2.5">
      <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3.5" />
        {title}
      </h4>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <Badge key={item} variant={variant} className="font-normal">
              {item}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyHint}</p>
      )}
    </div>
  );
}

function ListSection({
  icon: Icon,
  title,
  items,
}: {
  icon: React.ElementType;
  title: string;
  items: string[];
}) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-2.5">
      <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3.5" />
        {title}
      </h4>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
            <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground/50" />
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ContentDnaViewProps {
  dna: ContentDNA;
  /** Seek the video when a timestamped key moment is clicked. */
  onSeek?: (seconds: number) => void;
}

export function ContentDnaView({ dna, onSeek }: ContentDnaViewProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Dna className="size-4" />
            Content DNA
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            Source of truth for all generated content
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-7">
        {/* Top attribute tiles */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <AttributeTile
            icon={Film}
            label="Content Type"
            value={dna.content_type}
            accent="bg-blue-500/10 text-blue-600 dark:text-blue-400"
          />
          <AttributeTile
            icon={Users}
            label="Audience"
            value={dna.audience}
            accent="bg-violet-500/10 text-violet-600 dark:text-violet-400"
          />
          <AttributeTile
            icon={Palette}
            label="Tone"
            value={dna.tone}
            accent="bg-amber-500/10 text-amber-600 dark:text-amber-400"
          />
          <AttributeTile
            icon={Tag}
            label="Primary Topic"
            value={dna.primary_topic}
            accent="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          />
        </div>

        {/* Core message */}
        {dna.core_message && (
          <div className="rounded-xl border-l-2 border-primary bg-muted/40 px-5 py-4">
            <div className="flex items-center gap-1.5">
              <Quote className="size-3.5 text-muted-foreground" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Core Message
              </span>
            </div>
            <p className="mt-2 text-base font-medium leading-relaxed text-foreground">
              {dna.core_message}
            </p>
          </div>
        )}

        {/* Call to action */}
        {dna.cta && (
          <div className="flex items-start gap-3 rounded-xl border bg-card px-5 py-4">
            <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <Megaphone className="size-3.5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Call to Action
              </p>
              <p className="mt-1 text-sm text-foreground">{dna.cta}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-7 md:grid-cols-2">
          <ChipSection
            icon={Tag}
            title="Key Topics"
            items={dna.secondary_topics}
            emptyHint="No secondary topics identified"
          />
          <ChipSection
            icon={Sparkles}
            title="Keywords"
            items={dna.keywords}
            variant="outline"
            emptyHint="No keywords identified"
          />
        </div>

        {/* Hooks — highest-value output for social copy */}
        {dna.hooks.length > 0 && (
          <div className="space-y-2.5">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Sparkles className="size-3.5" />
              Potential Hooks
            </h4>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {dna.hooks.map((hook, i) => (
                <div
                  key={i}
                  className="rounded-lg border bg-gradient-to-br from-primary/5 to-transparent px-4 py-3 text-sm leading-relaxed text-foreground"
                >
                  &ldquo;{hook}&rdquo;
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-7 md:grid-cols-2">
          <ListSection
            icon={ListChecks}
            title="Key Points"
            items={dna.key_points}
          />
          <ListSection
            icon={Lightbulb}
            title="Important Concepts"
            items={dna.important_concepts}
          />
        </div>

        <ChipSection icon={AtSign} title="Entities" items={dna.entities} variant="outline" />

        {/* Key moments — clickable when anchored to a timestamp */}
        {dna.key_moments.length > 0 && (
          <div className="space-y-2.5">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="size-3.5" />
              Key Moments
              <span className="font-normal normal-case tracking-normal">
                ({dna.key_moments.length})
              </span>
            </h4>
            <div className="space-y-1.5">
              {dna.key_moments.map((moment, i) => {
                const seekable = moment.timestamp != null && onSeek;
                const Wrapper = seekable ? "button" : "div";
                return (
                  <Wrapper
                    key={i}
                    {...(seekable
                      ? {
                          type: "button" as const,
                          onClick: () => onSeek?.(moment.timestamp as number),
                        }
                      : {})}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left transition-colors",
                      seekable && "hover:border-primary/40 hover:bg-muted/60",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-xs tabular-nums",
                        moment.timestamp != null
                          ? "bg-primary/10 text-primary"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {moment.timestamp != null
                        ? formatTimestamp(moment.timestamp)
                        : "—"}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-foreground">
                        {moment.title}
                      </span>
                      {moment.description && (
                        <span className="mt-0.5 block text-sm leading-relaxed text-muted-foreground">
                          {moment.description}
                        </span>
                      )}
                    </span>
                  </Wrapper>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
