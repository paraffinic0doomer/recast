"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Wand2,
  FolderKanban,
  Megaphone,
  Library,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { AiEngineStatus } from "@/components/ai-engine-status";

const NAV = [
  { href: "/", label: "Studio", icon: Wand2 },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/assets", label: "Assets", icon: Library },
] as const;

function isActive(pathname: string, href: string) {
  // "/" must not light up for every route, and a project page belongs to Projects.
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-3 px-2" aria-label="RECAST home">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary shadow-lg shadow-primary/25">
        {/* The artwork is black ink on transparency, so it is inverted to
            white to sit on the indigo plate in either theme. */}
        <Image
          src="/recast-mark.png"
          alt=""
          width={36}
          height={36}
          priority
          className="size-7 invert"
        />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block text-[0.95rem] font-semibold tracking-tight text-sidebar-foreground">
          RECAST
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          Creative Studio
        </span>
      </span>
    </Link>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  // A project page is reached from Projects, so keep that section lit.
  const effective = pathname.startsWith("/projects/") ? "/projects" : pathname;

  return (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(effective, href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
              active
                ? "bg-sidebar-accent font-medium text-sidebar-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
            )}
          >
            {active && (
              <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />
            )}
            <Icon
              className={cn(
                "size-4 shrink-0 transition-colors",
                active ? "text-primary" : "text-muted-foreground group-hover:text-sidebar-foreground",
              )}
            />
            <span className="min-w-0 flex-1 truncate">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="pt-2">
        <Brand />
      </div>

      <div className="flex-1">
        <p className="px-3 pb-2 text-[0.6875rem] font-medium uppercase tracking-wider text-muted-foreground/70">
          Workspace
        </p>
        <NavLinks onNavigate={onNavigate} />
      </div>

      <div className="space-y-3">
        <AiEngineStatus />
        <div className="flex items-center justify-between gap-2 px-1">
          <span className="text-xs text-muted-foreground">Appearance</span>
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}

/**
 * Persistent workspace rail on desktop, slide-over on small screens. The rail
 * is what separates a tool from a page: the user is always somewhere in the
 * workspace rather than on a document.
 */
export function AppSidebar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const [seenPath, setSeenPath] = useState(pathname);

  // Close the mobile drawer whenever navigation actually happens. Adjusting
  // during render is React's documented pattern for state derived from props,
  // and it closes the drawer in the same paint as the new route.
  if (seenPath !== pathname) {
    setSeenPath(pathname);
    setOpen(false);
  }

  // Escape closes the drawer, and body scroll is locked while it is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-sidebar-border bg-sidebar lg:block">
        <SidebarBody />
      </aside>

      {/* Mobile bar */}
      <div className="sticky top-0 z-40 flex h-14 items-center justify-between gap-3 border-b border-sidebar-border bg-sidebar/90 px-4 backdrop-blur lg:hidden">
        <Brand />
        <div className="flex items-center gap-2">
          <AiEngineStatus collapsed />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-4" />
          </Button>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          />
          <div className="absolute inset-y-0 left-0 w-72 border-r border-sidebar-border bg-sidebar shadow-2xl">
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-3 top-3"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
            >
              <X className="size-4" />
            </Button>
            <SidebarBody onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
