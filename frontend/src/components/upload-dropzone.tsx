"use client";

import { useCallback, useRef, useState } from "react";
import { UploadCloud, Loader2, FileVideo, X } from "lucide-react";
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
      const project = await api.createProject(selectedFile.name.replace(/\.[^.]+$/, ""));
      await api.uploadVideo(project.id, selectedFile);
      toast.success("Video uploaded", {
        description: "Your project has been created.",
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

  if (selectedFile) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-primary/40 bg-primary/5 px-6 py-12 text-center">
        <div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
          {isUploading ? (
            <Loader2 className="size-6 animate-spin" />
          ) : (
            <FileVideo className="size-6" />
          )}
        </div>
        <div className="space-y-1">
          <p className="max-w-sm truncate text-sm font-medium text-foreground">
            {selectedFile.name}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatFileSize(selectedFile.size)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleUpload} disabled={isUploading}>
            {isUploading ? "Uploading…" : "Upload video"}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            disabled={isUploading}
            onClick={() => setSelectedFile(null)}
          >
            <X className="size-4" />
          </Button>
        </div>
      </div>
    );
  }

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
      className={cn(
        "group relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-16 text-center transition-colors cursor-pointer",
        isDragging
          ? "border-primary bg-primary/5"
          : "border-border hover:border-primary/50 hover:bg-muted/40",
      )}
    >
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

      <div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary transition-transform group-hover:scale-105">
        {isDragging ? (
          <FileVideo className="size-6" />
        ) : (
          <UploadCloud className="size-6" />
        )}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">
          Drop your video here, or click to browse
        </p>
        <p className="text-xs text-muted-foreground">
          MP4, MOV, AVI, MKV, or WEBM — up to 500MB
        </p>
      </div>
    </div>
  );
}
