import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });

  const lineStyle: React.CSSProperties = {
    fontSize: 24,
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 24,
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#eceff4",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "monospace",
        opacity,
      }}
    >
      <div>
        {/* Title */}
        <div
          style={{
            fontSize: 42,
            color: "#2e3440",
            fontWeight: "bold",
            marginBottom: 48,
          }}
        >
          agent-papers-cli
        </div>

        {/* pip install */}
        <div style={{ ...lineStyle, color: "#5e81ac" }}>
          <span style={{ fontSize: 28 }}>📦</span>
          <span>pip install agent-papers-cli</span>
        </div>

        {/* skills add */}
        <div style={{ ...lineStyle, color: "#a3be8c" }}>
          <span style={{ fontSize: 28 }}>🧩</span>
          <span>npx skills add collaborative-deep-research/agent-papers-cli</span>
        </div>

        {/* GitHub */}
        <div style={{ ...lineStyle, color: "#4c566a" }}>
          <span style={{ fontSize: 28 }}>⭐</span>
          <span>github.com/collaborative-deep-research/agent-papers-cli</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
