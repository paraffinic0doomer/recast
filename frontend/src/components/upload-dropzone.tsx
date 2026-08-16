"use client";

import { useCallback, useRef, useState } from "react";
import { UploadCloud, Loader2, FileVideo, X, Film, Sparkles } from "lucide-react";
import { cn, formatFileSize } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const ACCEPTED_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm"];
const MAX_SIZE_BYTES = 500 * 1024 * 1024;

interface UploadDropzoneProps {
  onUploaded: (projectId: string) => void;
}

function validateFile(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `Unsupported file type. Please upload one of: ${ACCEPTED_EXTENSIONS.join(", ")}`;
  }
  if (file.size > MAX_SIZE_BYTES) {
    return `File is too large (${formatFileSize(file.size)}). Maximum size is 500MB.`;
  }
  return null;
}

/** What RECAST will do with the file, shown before anything is dropped. */
const PROMISES = [
  "Transcribes every word",
  "Finds your best moments",
  "Cuts vertical shorts",
  "Writes for six platforms",
];

export function UploadDropzone({ onUploaded }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSelect = useCallback((file: File) => {
    const error = validateFile(file);
    if (error) {
      toast.error("Invalid file", { description: error });
      return;
    }
    setSelectedFile(file);
  }, []);

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    try {
      const project = await api.createProject(
        selectedFile.name.replace(/\.[^.]+$/, ""),
      );
      await api.uploadVideo(project.id, selectedFile);
      toast.success("Video uploaded", {
        description: "RECAST is starting to work on it now.",
      });
      setSelectedFile(null);
      onUploaded(project.id);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Upload failed";
      toast.error("Upload failed", { description: message });
    } finally {
      setIsUploading(false);
    }
  }, [selectedFile, onUploaded]);

  // --- staged file: confirm before sending -----------------------------------
  if (selectedFile) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-primary/40 bg-surface px-6 py-10">
        {isUploading && (
          <span className="absolute inset-x-0 top-0 h-0.5 ai-shimmer bg-primary/20" />
        )}
        <div className="flex flex-col items-center gap-5 text-center">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/12 text-primary">
            {isUploading ? (
              <Loader2 className="size-6 animate-spin" />
            ) : (
              <FileVideo className="size-6" />
            )}
          </div>
          <div className="min-w-0 space-y-1">
            <p className="mx-auto max-w-md break-all text-[0.95rem] font-medium text-foreground">
              {selectedFile.name}
            </p>
            <p className="font-mono text-xs text-muted-foreground">
              {formatFileSize(selectedFile.size)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button size="lg" onClick={handleUpload} disabled={isUploading}>
              {isUploading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Sparkles className="size-4" />
                  Start creating
                </>
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              disabled={isUploading}
              onClick={() => setSelectedFile(null)}
              aria-label="Choose a different file"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // --- empty dropzone --------------------------------------------------------
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file) handleSelect(file);
      }}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label="Upload a video"
      className={cn(
        "group relative cursor-pointer overflow-hidden rounded-2xl border border-dashed px-6 py-14 text-center transition-all duration-300",
        "focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        isDragging
          ? "border-primary bg-primary/[0.06] ai-glow"
          : "border-border bg-surface/50 hover:border-primary/50 hover:bg-surface",
      )}
    >
      {/* The sweep only runs while a file is actually over the target. */}
      {isDragging && <span className="absolute inset-0 ai-shimmer" />}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleSelect(file);
          e.target.value = "";
        }}
      />

      <div className="relative flex flex-col items-center gap-5">
        <div
          className={cn(
            "flex size-16 items-center justify-center rounded-2xl transition-all duration-300",
            isDragging
              ? "scale-110 bg-primary text-primary-foreground"
              : "bg-primary/10 text-primary group-hover:scale-105",
          )}
        >
          {isDragging ? (
            <Film className="size-7" />
          ) : (
            <UploadCloud className="size-7" />
          )}
        </div>

        <div className="space-y-1.5">
          <p className="text-lg font-semibold text-foreground">
            {isDragging ? "Drop to begin" : "Drop your video here"}
          </p>
          <p className="text-sm text-muted-foreground">
            or{" "}
            <span className="font-medium text-primary underline-offset-4 group-hover:underline">
              browse your files
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          {["MP4", "MOV", "AVI", "MKV", "WEBM"].map((format) => (
            <span
              key={format}
              className="rounded-md bg-secondary px-2 py-1 font-mono text-[0.6875rem] tracking-wide text-muted-foreground"
            >
              {format}
            </span>
          ))}
          <span className="text-xs text-muted-foreground">up to 500MB</span>
        </div>

        <div className="mt-1 flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5 border-t border-border/60 pt-5 text-xs text-muted-foreground">
          {PROMISES.map((promise) => (
            <span key={promise} className="flex items-center gap-1.5">
              <span className="size-1 rounded-full bg-primary" />
              {promise}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
