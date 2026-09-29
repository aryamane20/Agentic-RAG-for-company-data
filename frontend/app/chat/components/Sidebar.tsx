import type { ConversationSummary } from "@/lib/backend";

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14"></path>
    <path d="M12 5v14"></path>
  </svg>
);

const LogoutIcon = () => (
  <svg style={{ marginLeft: "auto", color: "var(--color-neutral-600)" }} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
    <polyline points="16 17 21 12 16 7"></polyline>
    <line x1="21" x2="9" y1="12" y2="12"></line>
  </svg>
);

interface SidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  badge: string;
  initial: string;
  onLogout: () => void;
}

export default function Sidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  badge,
  initial,
  onLogout,
}: SidebarProps) {
  return (
    <aside
      style={{
        background: "var(--color-bg)",
        borderRight: "1px solid var(--color-divider)",
        display: "flex",
        flexDirection: "column",
        padding: "22px 16px 18px",
        gap: 22,
        minHeight: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "0 8px" }}>
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: "50%",
            background: "var(--color-accent)",
            boxShadow: "inset -8px -8px 0 0 var(--color-accent-700)",
          }}
        />
        <div style={{ fontFamily: "var(--font-heading)", fontSize: 18, lineHeight: 1 }}>Solstice</div>
      </div>

      <button
        type="button"
        className="btn btn-secondary"
        onClick={onNewConversation}
        style={{
          justifyContent: "flex-start",
          gap: 8,
          fontFamily: "var(--font-body)",
          fontWeight: 600,
          fontSize: 14,
          padding: "9px 14px",
          background: activeConversationId === null ? "var(--color-neutral-300)" : "var(--color-neutral-100)",
        }}
      >
        <PlusIcon />
        New conversation
      </button>

      <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, minHeight: 0, overflowY: "auto" }}>
        <div
          style={{
            fontSize: 11,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--color-neutral-700)",
            padding: "0 12px 8px",
          }}
        >
          Recent
        </div>
        {conversations.length === 0 && (
          <div style={{ fontSize: 13, color: "var(--color-neutral-600)", padding: "0 12px" }}>
            No conversations yet
          </div>
        )}
        {conversations.map((conversation) => {
          const active = conversation.id === activeConversationId;
          return (
            <button
              key={conversation.id}
              type="button"
              onClick={() => onSelectConversation(conversation.id)}
              style={{
                textAlign: "left",
                font: "inherit",
                fontSize: 14,
                fontWeight: active ? 600 : 400,
                padding: "8px 12px",
                borderRadius: 999,
                border: "none",
                cursor: "pointer",
                background: active ? "var(--color-neutral-300)" : "transparent",
                color: "var(--color-neutral-800)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {conversation.title}
            </button>
          );
        })}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 8px 0",
          borderTop: "1px solid var(--color-divider)",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "var(--color-accent-2-300)",
            color: "var(--color-accent-2-900)",
            display: "grid",
            placeItems: "center",
            fontWeight: 700,
            fontSize: 14,
          }}
        >
          {initial}
        </div>
        <span className="tag tag-accent-2" style={{ fontSize: 12, padding: "4px 11px" }}>
          {badge}
        </span>
        <button
          type="button"
          onClick={onLogout}
          aria-label="Log out"
          style={{ background: "none", border: "none", cursor: "pointer", display: "flex", marginLeft: "auto" }}
        >
          <LogoutIcon />
        </button>
      </div>
    </aside>
  );
}
