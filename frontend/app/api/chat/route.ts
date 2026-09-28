import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, SESSION_COOKIE } from "@/lib/backend";

// Reads the JWT from the httpOnly cookie (server-side only) and attaches
// it as Authorization: Bearer when forwarding to FastAPI /chat. The
// browser sends this route a plain-cookie request with no token visible
// to it at any point.
export async function POST(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  let body: { message?: string; conversation_id?: string; message_id?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  if (!body.message) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        message: body.message,
        conversation_id: body.conversation_id,
        message_id: body.message_id,
      }),
    });
  } catch {
    return NextResponse.json({ error: "Unable to reach the backend" }, { status: 502 });
  }

  const data = await backendResponse.json();

  if (!backendResponse.ok) {
    if (backendResponse.status === 401) {
      const response = NextResponse.json({ error: "Session expired" }, { status: 401 });
      response.cookies.delete(SESSION_COOKIE);
      return response;
    }
    return NextResponse.json(data, { status: backendResponse.status });
  }

  return NextResponse.json(data);
}
