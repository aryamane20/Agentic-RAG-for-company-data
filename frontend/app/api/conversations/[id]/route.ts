import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, SESSION_COOKIE } from "@/lib/backend";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const { id } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_URL}/conversations/${encodeURIComponent(id)}`, {
      headers: { Authorization: `Bearer ${token}` },
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
