"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

/** Segmented light / dark / system switch. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  // The server cannot know the stored theme, so the first client render must
  // match the server (nothing active) and only then reveal the real selection.
  // react-hooks/set-state-in-effect flags this, but the one-shot mount flag is
  // the documented next-themes pattern: without it React reports a hydration
  // mismatch on aria-pressed and className.
  const [mounted, setMounted] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  return (
    <div
      className="flex items-center gap-0.5 rounded-lg border bg-card p-0.5"
      role="group"
      aria-label="Colour theme"
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => setTheme(value)}
            aria-label={label}
            aria-pressed={active}
            title={label}
            className={cn(
              "flex size-7 items-center justify-center rounded-md transition-colors",
              active
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}
