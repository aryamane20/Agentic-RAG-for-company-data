"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        setError(
          "That username and password don’t match. Try again, or contact IT if you’re locked out.",
        );
        setSubmitting(false);
        return;
      }

      router.push("/chat");
      router.refresh();
    } catch {
      setError("Unable to reach the server. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100dvh",
        background: "var(--color-bg)",
        display: "grid",
        placeItems: "center",
        padding: "var(--space-4)",
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: 380,
          maxWidth: "100%",
          background: "var(--color-neutral-100)",
          border: "1px solid var(--color-divider)",
          borderRadius: "var(--radius-lg)",
          padding: "40px 36px 32px",
          display: "flex",
          flexDirection: "column",
          gap: 28,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: "50%",
                background: "var(--color-accent)",
                boxShadow: "inset -9px -9px 0 0 var(--color-accent-700)",
              }}
            />
            <div style={{ fontFamily: "var(--font-heading)", fontSize: 21, lineHeight: 1 }}>
              Solstice Analytics
            </div>
          </div>
          <div style={{ fontSize: 14, color: "var(--color-neutral-700)" }}>
            Internal knowledge assistant
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="field">
            <label htmlFor="email">Username</label>
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={error ? { borderColor: "var(--color-accent-400)" } : undefined}
              required
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-block"
            style={{ minHeight: 42, fontSize: 15, marginTop: 6 }}
            disabled={submitting}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
          {error && (
            <div
              style={{
                fontSize: 13,
                lineHeight: 1.45,
                color: "var(--color-accent-700)",
                textAlign: "center",
              }}
            >
              {error}
            </div>
          )}
        </div>
      </form>
    </div>
  );
}
