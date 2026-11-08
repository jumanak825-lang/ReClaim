import { api, ApiError, unwrap, type Schemas } from "./client";

export type Image = Schemas["ImageOut"];
export type ImageVisibility = Image["visibility"];

export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;

/**
 * Upload one photo. Type and size are checked here for fast feedback; the API re-checks the
 * real file signature and is the authority (docs/08 §8.8).
 */
export async function uploadImage(file: File, visibility: ImageVisibility): Promise<Image> {
  if (!IMAGE_TYPES.includes(file.type)) {
    throw new ApiError(415, "UNSUPPORTED_FILE_TYPE", "Use a JPEG, PNG or WebP photo.");
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new ApiError(413, "FILE_TOO_LARGE", "Photos must be 8 MB or smaller.");
  }
  const form = new FormData();
  form.append("file", file);
  form.append("visibility", visibility);
  return unwrap(
    api.POST("/api/v1/uploads", {
      // The typed body describes the multipart fields; send the FormData as-is.
      body: { file: "", visibility },
      bodySerializer: () => form,
    }),
  );
}

/** User-facing message for upload failures, keyed on the server's stable error codes. */
export function uploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "UNSUPPORTED_FILE_TYPE":
      case "FILE_SIGNATURE_MISMATCH":
        return "That file isn't a JPEG, PNG or WebP photo.";
      case "FILE_TOO_LARGE":
        return "Photos must be 8 MB or smaller.";
      case "EMPTY_FILE":
        return "That file is empty.";
    }
  }
  return "We couldn't upload that photo. Try again.";
}
