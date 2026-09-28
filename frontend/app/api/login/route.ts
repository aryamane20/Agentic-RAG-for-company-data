import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, SESSION_COOKIE, SESSION_MAX_AGE_SECONDS } from "@/lib/backend";

// Calls FastAPI /login server-side and stores the JWT as an httpOnly
// cookie -- the browser (and any client-side JS) never sees the raw
// token, only this route's {ok:true} response.
export async function POST(request: NextRequest) {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  if (!body.email || !body.password) {
    return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password }),
    });
  } catch {
    return NextResponse.json({ error: "Unable to reach the backend" }, { status: 502 });
  }

  if (!backendResponse.ok) {
    const status = backendResponse.status === 401 ? 401 : backendResponse.status;
    return NextResponse.json(
      { error: status === 401 ? "Invalid email or password" : "Login failed" },
      { status },
    );
  }

  const data: { access_token: string } = await backendResponse.json();

  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  return response;
}
