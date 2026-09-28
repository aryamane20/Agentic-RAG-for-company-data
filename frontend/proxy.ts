import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/backend";

// Gate every page except /login itself. No token verification here (the
// JWT's signature/expiry is checked server-side by FastAPI on every
// request that matters) -- this only redirects when the cookie is
// missing, so a signed-out visitor lands on the login page instead of a
// broken chat screen or an error.
export function proxy(request: NextRequest) {
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  const isLoginPage = request.nextUrl.pathname === "/login";

  if (!hasSession && !isLoginPage) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (hasSession && isLoginPage) {
    return NextResponse.redirect(new URL("/chat", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
