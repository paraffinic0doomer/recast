import { cn } from "@/lib/utils";

/**
 * Circular score readout.
 *
 * The stroke colour is written as a literal class per band rather than built
 * from a string, because Tailwind only ships classes it can see in the source.
 */
function band(value: number) {
  if (value >= 85) return { stroke: "stroke-success", text: "text-success" };
  if (value >= 70) return { stroke: "stroke-primary", text: "text-primary" };
  if (value >= 50) return { stroke: "stroke-warning", text: "text-warning" };
  return { stroke: "stroke-destructive", text: "text-destructive" };
}

export function ScoreRing({
  value,
  size = 64,
  label,
  className,
}: {
  value: number;
  size?: number;
  label?: string;
  className?: string;
}) {
  // Scores arrive as floats from the completeness calculation; the ring shows
  // a whole number so it never renders "75.3" in a 44px circle.
  const clamped = Math.round(Math.max(0, Math.min(100, value)));
  const stroke = size >= 60 ? 5 : 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const tone = band(clamped);

  return (
    <div className={cn("flex shrink-0 items-center gap-2.5", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-90"
          role="img"
          aria-label={`${label ?? "Score"}: ${clamped} out of 100`}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            className="stroke-secondary"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - clamped / 100)}
            className={cn(tone.stroke, "transition-[stroke-dashoffset] duration-700 ease-out")}
          />
        </svg>
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center font-mono tabular-nums",
            tone.text,
            size >= 60 ? "text-base font-medium" : "text-xs font-medium",
          )}
        >
          {clamped}
        </span>
      </div>
      {label && size >= 60 && (
        <span className="text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {label}
        </span>
      )}
    </div>
  );
}
