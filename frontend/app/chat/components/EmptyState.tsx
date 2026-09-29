import type { ExamplePrompt } from "../examples";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

interface EmptyStateProps {
  name: string;
  examples: ExamplePrompt[];
  onSelectExample: (prompt: ExamplePrompt) => void;
}

export default function EmptyState({ name, examples, onSelectExample }: EmptyStateProps) {
  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 32px" }}>
      <div style={{ width: "100%", maxWidth: 600, display: "flex", flexDirection: "column", gap: 28 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <h2 style={{ margin: 0, fontSize: 34 }}>
            {greeting()}, {name}
          </h2>
          <div style={{ fontSize: 15, color: "var(--color-neutral-700)" }}>
            Ask anything about the Solstice documents you have access to. A few places to start:
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {examples.map((example) => (
            <button
              key={example.text}
              type="button"
              onClick={() => onSelectExample(example)}
              style={{
                textAlign: "left",
                font: "inherit",
                fontSize: 14,
                lineHeight: 1.45,
                color: "var(--color-text)",
                background: "var(--color-bg)",
                border: "1px solid var(--color-divider)",
                borderRadius: "var(--radius-md)",
                padding: "14px 16px",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "var(--color-accent-2-700)",
                }}
              >
                {example.doc}
              </span>
              <span>{example.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
