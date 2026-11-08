/**
 * Accept a post-sign-in redirect target only if it is a path on this site.
 * Rejects absolute URLs, protocol-relative "//evil.com" and "/\evil.com" (open redirect).
 */
export function safeNext(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return null;
  return value;
}
