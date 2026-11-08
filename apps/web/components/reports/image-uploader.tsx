"use client";

import { useId, useState } from "react";
import { ImagePlus, Loader2, X } from "lucide-react";
import { IMAGE_TYPES, uploadErrorMessage, uploadImage, type Image, type ImageVisibility } from "@/lib/api/uploads";
import { Button } from "@/components/ui/button";

const MAX_IMAGES = 6;

/** Photo picker that uploads immediately and reports the uploaded images to the parent. */
export function ImageUploader({
  label,
  hint,
  visibility,
  images,
  onChange,
}: {
  label: string;
  hint: string;
  visibility: ImageVisibility;
  images: Image[];
  onChange: (images: Image[]) => void;
}) {
  const inputId = useId();
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    const room = MAX_IMAGES - images.length;
    const picked = Array.from(files).slice(0, room);
    if (files.length > room) setError(`You can add up to ${MAX_IMAGES} photos.`);
    setUploading((n) => n + picked.length);
    const added: Image[] = [];
    for (const file of picked) {
      try {
        added.push(await uploadImage(file, visibility));
      } catch (e) {
        setError(`${file.name}: ${uploadErrorMessage(e)}`);
      } finally {
        setUploading((n) => n - 1);
      }
    }
    if (added.length) onChange([...images, ...added]);
  }

  return (
    <div className="grid gap-2">
      <p className="text-sm font-medium" id={`${inputId}-label`}>
        {label}
      </p>
      <p className="text-sm text-muted-foreground">{hint}</p>
      <ul className="flex flex-wrap gap-3" aria-label="Uploaded photos">
        {images.map((img, i) => (
          <li key={img.id} className="relative">
            {/* Same-origin, session-authorised URL from the API. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img.url} alt={`Photo ${i + 1}`} className="size-24 rounded-md border object-cover" />
            <Button
              type="button"
              size="icon"
              variant="secondary"
              className="absolute -top-2 -right-2 size-7 rounded-full"
              aria-label={`Remove photo ${i + 1}`}
              onClick={() => onChange(images.filter((x) => x.id !== img.id))}
            >
              <X aria-hidden />
            </Button>
          </li>
        ))}
      </ul>
      {images.length < MAX_IMAGES && (
        <div>
          <label
            htmlFor={inputId}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-dashed px-4 py-3 text-sm hover:bg-muted focus-within:ring-2 focus-within:ring-ring"
          >
            {uploading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <ImagePlus className="size-4" aria-hidden />}
            {uploading ? "Uploading…" : "Add photos"}
            <input
              id={inputId}
              type="file"
              accept={IMAGE_TYPES.join(",")}
              multiple
              className="sr-only"
              aria-describedby={`${inputId}-label`}
              disabled={uploading > 0}
              onChange={(e) => {
                void handleFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      )}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
