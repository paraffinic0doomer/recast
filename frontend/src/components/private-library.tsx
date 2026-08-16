import { EyeOff } from "lucide-react";
import { EmptyState } from "@/components/workspace";

/**
 * Shown in place of a listing on a public build.
 *
 * Deliberately states that content exists but is not browsable, rather than
 * implying the workspace is empty — a visitor should understand they are
 * looking at a private library, not a broken page.
 */
export function PrivateLibrary({ what = "Projects" }: { what?: string }) {
  return (
    <EmptyState
      icon={EyeOff}
      title={`${what} are private`}
      description="This workspace doesn't list its library publicly. Open a project directly with its link, or upload a video to create your own."
    />
  );
}
