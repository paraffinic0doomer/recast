import Image from "next/image";
import Link from "next/link";
import { Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-6 px-6 py-24 text-center">
      {/* Black ink on transparency: inverted in dark, left as-is in light. */}
      <Image
        src="/recast-lockup.png"
        alt="RECAST"
        width={264}
        height={128}
        className="h-12 w-auto opacity-70 dark:invert"
      />
      <div className="space-y-2">
        <h1 className="text-xl font-semibold tracking-tight">Page not found</h1>
        <p className="text-sm text-muted-foreground">
          That page doesn&apos;t exist. It may have been a project that was
          deleted.
        </p>
      </div>
      <Button asChild>
        <Link href="/">
          <Home className="size-4" />
          Back to the Studio
        </Link>
      </Button>
    </main>
  );
}
