import { NextResponse, type NextRequest } from "next/server";

// Optimistic check only: no session cookie means "not signed in", so skip rendering the
// protected page. The API stays authoritative. Protected layouts still verify via GET /me.
export function proxy(request: NextRequest) {
  if (request.cookies.has("reclaim_session")) return NextResponse.next();
  const url = new URL("/sign-in", request.url);
  url.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/dashboard/:path*", "/report/:path*", "/org/:path*"],
};
