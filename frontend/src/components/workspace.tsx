import { cn } from "@/lib/utils";

/** Consistent page gutter and rhythm for every route in the workspace. */
export function Page({
  children,
  className,
  wide = false,
}: {
  children: React.ReactNode;
  className?: string;
  wide?: boolean;
}) {
  return (
    <main
      className={cn(
        "mx-auto w-full flex-1 px-5 py-8 sm:px-8 sm:py-12",
        wide ? "max-w-[1400px]" : "max-w-6xl",
        className,
      )}
    >
      {children}
    </main>
  );
}

/** Page title block: eyebrow, title, one line of context, optional action. */
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end justify-between gap-x-8 gap-y-4",
        className,
      )}
    >
      <div className="min-w-0 space-y-2">
        {eyebrow && (
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="text-[1.75rem] leading-tight text-foreground sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="max-w-2xl text-[0.95rem] text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

/** Section heading inside a page — smaller than a PageHeader, same grammar. */
export function SectionHeader({
  title,
  count,
  description,
  action,
}: {
  title: string;
  count?: number;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
      <div className="min-w-0">
        <h2 className="flex items-center gap-2.5 text-lg font-semibold text-foreground">
          {title}
          {count != null && count > 0 && (
            <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-xs tabular-nums text-muted-foreground">
              {count}
            </span>
          )}
        </h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/**
 * The empty state used everywhere. Deliberately generous: an empty workspace
 * is the first thing a judge sees, so it explains the next action instead of
 * apologising for having no data.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  tone = "default",
}: {
  icon: React.ElementType;
  title: string;
  description?: string;
  action?: React.ReactNode;
  tone?: "default" | "pending";
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border bg-surface/40 px-6 py-16 text-center">
      <div
        className={cn(
          "flex size-12 items-center justify-center rounded-2xl",
          tone === "pending"
            ? "bg-primary/10 text-primary"
            : "bg-secondary text-muted-foreground",
        )}
      >
        <Icon className="size-5" />
      </div>
      <div className="space-y-1.5">
        <p className="text-base font-semibold text-foreground">{title}</p>
        {description && (
          <p className="mx-auto max-w-sm text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

/** Small uppercase label above a value. Used across every detail panel. */
export function FieldLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}
