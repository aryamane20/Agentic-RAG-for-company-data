import type { ChatMessage } from "../types";

function formatTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

const DocIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path>
    <path d="M14 2v4a2 2 0 0 0 2 2h4"></path>
  </svg>
);

const LockIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round">
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2"></rect>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
  </svg>
);

export default function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div
          style={{
            maxWidth: "70%",
            background: "var(--color-accent-100)",
            color: "var(--color-accent-900)",
            padding: "10px 16px",
            borderRadius: "20px 20px 6px 20px",
            fontSize: 15,
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  if (message.isDenial) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 640 }}>
        <div
          style={{
            display: "flex",
            gap: 14,
            alignItems: "flex-start",
            background: "var(--color-neutral-200)",
            border: "1px solid var(--color-divider)",
            borderRadius: "var(--radius-md)",
            padding: "16px 18px",
          }}
        >
          <div
            style={{
              width: 30,
              height: 30,
              flex: "none",
              borderRadius: "50%",
              background: "var(--color-neutral-100)",
              display: "grid",
              placeItems: "center",
              color: "var(--color-neutral-700)",
            }}
          >
            <LockIcon />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--color-neutral-900)" }}>
              {message.text}
            </div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--color-neutral-600)", paddingLeft: 4 }}>
          {formatTime(message.timestamp)}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 640 }}>
      <div style={{ fontSize: 15, lineHeight: 1.65, whiteSpace: "pre-wrap" }}>{message.text}</div>
      {(message.sourceDocuments?.length ?? 0) > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
          {message.sourceDocuments!.map((doc) => (
            <span
              key={doc}
              className="tag tag-neutral"
              style={{ gap: 6, border: "1px solid var(--color-divider)", color: "var(--color-neutral-700)" }}
            >
              <DocIcon />
              Source: {doc}
            </span>
          ))}
          <span style={{ fontSize: 12, color: "var(--color-neutral-600)" }}>
            {formatTime(message.timestamp)}
          </span>
        </div>
      )}
    </div>
  );
}
