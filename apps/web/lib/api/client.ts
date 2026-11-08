import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

/** Typed client for the Reclaim API. Paths come from apps/api/openapi.json (`npm run gen:api`). */
export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" });

export type Schemas = components["schemas"];
type ErrorEnvelope = Schemas["ErrorEnvelope"];

/** An API error carrying the server's stable code (docs/05 §5.1). Branch on `code`, never on `message`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Return the `data` payload of a success envelope, or throw an ApiError. */
export async function unwrap<T>(request: Promise<Result<{ data: T }>>): Promise<T> {
  const { data, error, response } = await request;
  if (data) return data.data;
  throw toApiError(error, response);
}

/** For endpoints that don't use the envelope (health, 204s). */
export async function unwrapRaw<T>(request: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (response.ok) return data as T;
  throw toApiError(error, response);
}

function toApiError(error: unknown, response: Response): ApiError {
  const body = error as Partial<ErrorEnvelope> | undefined;
  if (body?.error) {
    return new ApiError(
      response.status,
      body.error.code,
      body.error.message,
      body.error.details,
      body.meta?.request_id,
    );
  }
  return new ApiError(response.status, "NETWORK_ERROR", "We couldn't reach Reclaim. Try again.");
}
