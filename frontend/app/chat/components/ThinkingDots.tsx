const DELAYS = [0, 0.15, 0.3];

export default function ThinkingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 5, padding: "8px 0" }}>
      {DELAYS.map((delay) => (
        <span
          key={delay}
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "var(--color-neutral-600)",
            display: "inline-block",
            animation: `solDot 1.2s ${delay}s infinite ease-in-out`,
          }}
        />
      ))}
    </span>
  );
}
