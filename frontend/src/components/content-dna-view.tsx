"use client";

import {
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
import { SectionHeader, FieldLabel } from "@/components/workspace";
import { cn } from "@/lib/utils";
import type { ContentDNA } from "@/types/project";

function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** One high-signal attribute of the content. */
function AttributeCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center gap-2.5">
        <span className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-3.5" />
        </span>
        <FieldLabel>{label}</FieldLabel>
      </div>
      {/* These values are phrases, not labels, so they wrap rather than clip. */}
      <p className="mt-3 text-[0.95rem] font-medium leading-snug text-foreground">
        {value || <span className="text-muted-foreground">Not identified</span>}
      </p>
    </div>
  );
}

function Chips({
  icon: Icon,
  title,
  items,
  emptyHint,
}: {
  icon: React.ElementType;
  title: string;
  items: string[];
  emptyHint?: string;
}) {
  if (items.length === 0 && !emptyHint) return null;
  return (
    <div className="space-y-3">
      <h4 className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Icon className="size-3.5 text-muted-foreground" />
        {title}
      </h4>
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item}
              className="rounded-lg border border-border bg-surface px-2.5 py-1 text-sm text-foreground"
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyHint}</p>
      )}
    </div>
  );
}

function Points({
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
    <div className="space-y-3">
      <h4 className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Icon className="size-3.5 text-muted-foreground" />
        {title}
      </h4>
      <ul className="space-y-2.5">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
            <span className="mt-2 size-1 shrink-0 rounded-full bg-primary" />
            <span>{item}</span>
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

/**
 * The AI's understanding report. Never raw JSON: every field is presented as
 * something a creator can read and act on, in the order they'd care about it.
 */
export function ContentDnaView({ dna, onSeek }: ContentDnaViewProps) {
  return (
    <section className="space-y-8">
      <SectionHeader
        title="Content DNA"
        description="What RECAST understood about your video. Every generated post, short and thumbnail is written from this."
      />

      {/* What it is */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AttributeCard icon={Film} label="Content type" value={dna.content_type} />
        <AttributeCard icon={Users} label="Audience" value={dna.audience} />
        <AttributeCard icon={Palette} label="Tone" value={dna.tone} />
        <AttributeCard icon={Tag} label="Primary topic" value={dna.primary_topic} />
      </div>

      {/* The single most important sentence on the page */}
      {dna.core_message && (
        <div className="rounded-2xl border border-primary/25 bg-primary/[0.05] px-6 py-5">
          <div className="flex items-center gap-2">
            <Quote className="size-3.5 text-primary" />
            <FieldLabel className="text-primary">Core message</FieldLabel>
          </div>
          <p className="mt-3 text-lg font-medium leading-relaxed text-foreground">
            {dna.core_message}
          </p>
        </div>
      )}

      {dna.cta && (
        <div className="flex items-start gap-4 rounded-2xl border border-border bg-card px-5 py-4">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-warning/12 text-warning">
            <Megaphone className="size-4" />
          </span>
          <div className="min-w-0">
            <FieldLabel>Call to action</FieldLabel>
            <p className="mt-1 text-sm leading-relaxed text-foreground">{dna.cta}</p>
          </div>
        </div>
      )}

      {/* Hooks — the highest-value output for social copy */}
      {dna.hooks.length > 0 && (
        <div className="space-y-3">
          <h4 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Sparkles className="size-3.5 text-primary" />
            Potential hooks
          </h4>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {dna.hooks.map((hook, i) => (
              <div
                key={i}
                className="rounded-xl border border-border bg-surface px-4 py-3.5 text-sm leading-relaxed text-foreground"
              >
                &ldquo;{hook}&rdquo;
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <Points icon={ListChecks} title="Key points" items={dna.key_points} />
        <Points icon={Lightbulb} title="Important concepts" items={dna.important_concepts} />
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <Chips
          icon={Tag}
          title="Key topics"
          items={dna.secondary_topics}
          emptyHint="No secondary topics identified"
        />
        <Chips
          icon={Sparkles}
          title="Keywords"
          items={dna.keywords}
          emptyHint="No keywords identified"
        />
      </div>

      <Chips icon={AtSign} title="Entities" items={dna.entities} />

      {/* Key moments — clickable when anchored to a timestamp */}
      {dna.key_moments.length > 0 && (
        <div className="space-y-3">
          <h4 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Clock className="size-3.5 text-muted-foreground" />
            Key moments
            <span className="font-mono text-xs tabular-nums text-muted-foreground">
              {dna.key_moments.length}
            </span>
          </h4>
          <div className="space-y-2">
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
                    "flex w-full items-start gap-3.5 rounded-xl border border-border bg-card px-4 py-3.5 text-left transition-colors",
                    seekable && "hover:border-primary/40 hover:bg-surface",
                  )}
                >
                  <span
                    className={cn(
                      "mt-px shrink-0 rounded-md px-2 py-1 font-mono text-xs tabular-nums",
                      moment.timestamp != null
                        ? "bg-primary/12 text-primary"
                        : "bg-secondary text-muted-foreground",
                    )}
                  >
                    {moment.timestamp != null ? formatTimestamp(moment.timestamp) : "—"}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-foreground">
                      {moment.title}
                    </span>
                    {moment.description && (
                      <span className="mt-1 block text-sm leading-relaxed text-muted-foreground">
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
    </section>
  );
}
