"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { REFUSAL_TEXT, type MeResponse } from "@/lib/backend";
import { EXAMPLE_PROMPTS, ROLE_LABELS, type ExamplePrompt } from "./examples";
import type { ChatMessage, Conversation } from "./types";
import Sidebar from "./components/Sidebar";
import EmptyState from "./components/EmptyState";
import MessageBubble from "./components/MessageBubble";
import ThinkingDots from "./components/ThinkingDots";

const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="m5 12 7-7 7 7"></path>
    <path d="M12 19V5"></path>
  </svg>
);

function truncateTitle(text: string) {
  return text.length > 48 ? `${text.slice(0, 48)}…` : text;
}

export default function ChatPage() {
  const router = useRouter();
  const [user, setUser] = useState<MeResponse | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch("/api/me")
      .then((res) => {
        if (!res.ok) throw new Error("unauthenticated");
        return res.json();
      })
      .then((data: MeResponse) => setUser(data))
      .catch(() => router.push("/login"));
  }, [router]);

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  );

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ block: "end" });
  }, [activeConversation?.messages.length, sending]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending || !user) return;

    let conversationId = activeConversationId;
    const isNewConversation = conversationId === null;
    if (isNewConversation) {
      conversationId = crypto.randomUUID();
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: trimmed,
      timestamp: Date.now(),
    };

    setConversations((prev) => {
      if (isNewConversation) {
        return [
          { id: conversationId!, title: truncateTitle(trimmed), messages: [userMessage] },
          ...prev,
        ];
      }
      return prev.map((c) =>
        c.id === conversationId ? { ...c, messages: [...c.messages, userMessage] } : c,
      );
    });
    setActiveConversationId(conversationId);
    setInput("");
    setSending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          conversation_id: conversationId,
          message_id: crypto.randomUUID(),
        }),
      });

      if (response.status === 401) {
        router.push("/login");
        return;
      }

      const data = await response.json();
      const answer: string = data.answer ?? "Something went wrong. Please try again.";
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: answer,
        sourceDocuments: data.source_documents ?? [],
        isDenial: answer === REFUSAL_TEXT,
        timestamp: Date.now(),
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId ? { ...c, messages: [...c.messages, assistantMessage] } : c,
        ),
      );
    } catch {
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: "Something went wrong reaching the server. Please try again.",
        timestamp: Date.now(),
      };
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId ? { ...c, messages: [...c.messages, errorMessage] } : c,
        ),
      );
    } finally {
      setSending(false);
    }
  }

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  function handleSelectExample(example: ExamplePrompt) {
    setInput(example.text);
  }

  if (!user) {
    return (
      <div style={{ minHeight: "100dvh", display: "grid", placeItems: "center", background: "var(--color-neutral-100)" }}>
        <ThinkingDots />
      </div>
    );
  }

  const badge = `${user.name} · ${ROLE_LABELS[user.role]}`;
  const firstName = user.name.split(" ")[0];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "272px minmax(0, 1fr)",
        height: "100dvh",
        background: "var(--color-neutral-100)",
      }}
    >
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversationId}
        onNewConversation={() => setActiveConversationId(null)}
        badge={badge}
        initial={user.name.charAt(0).toUpperCase()}
        onLogout={handleLogout}
      />

      <main style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <header
          style={{
            height: 60,
            flex: "none",
            display: "flex",
            alignItems: "center",
            padding: "0 32px",
            borderBottom: "1px solid var(--color-divider)",
          }}
        >
          <div
            style={{
              fontSize: 15,
              fontWeight: activeConversation ? 600 : 400,
              color: activeConversation ? "var(--color-text)" : "var(--color-neutral-700)",
            }}
          >
            {activeConversation?.title ?? "New conversation"}
          </div>
        </header>

        {!activeConversation ? (
          <EmptyState name={firstName} examples={EXAMPLE_PROMPTS[user.role]} onSelectExample={handleSelectExample} />
        ) : (
          <div style={{ flex: 1, minHeight: 0, overflow: "auto", display: "flex", justifyContent: "center" }}>
            <div style={{ width: "100%", maxWidth: 760, padding: "24px 32px 20px", display: "flex", flexDirection: "column", gap: 22 }}>
              {activeConversation.messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {sending && (
                <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--color-neutral-600)", fontSize: 13 }}>
                  <ThinkingDots />
                  <span>Searching…</span>
                </div>
              )}
              <div ref={threadEndRef} />
            </div>
          </div>
        )}

        <div style={{ flex: "none", display: "flex", justifyContent: "center", padding: "0 32px 22px" }}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            style={{ width: "100%", maxWidth: 696, display: "flex", flexDirection: "column", gap: 8 }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "var(--color-neutral-100)",
                border: "1px solid var(--color-neutral-400)",
                borderRadius: 999,
                padding: "6px 6px 6px 20px",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question…"
                style={{
                  flex: 1,
                  fontSize: 15,
                  color: "var(--color-text)",
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  font: "inherit",
                }}
              />
              <button
                type="submit"
                className="btn btn-primary btn-icon"
                style={{ borderRadius: "50%" }}
                disabled={!input.trim() || sending}
              >
                <SendIcon />
              </button>
            </div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-600)", textAlign: "center" }}>
              Answers come only from documents your role can access.
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
