import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#1e1e2e",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "monospace",
        opacity,
      }}
    >
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            fontSize: 28,
            color: "#cdd6f4",
            fontWeight: "bold",
            marginBottom: 32,
          }}
        >
          agent-papers-cli
        </div>

        <div style={{ fontSize: 18, color: "#89b4fa", marginBottom: 16 }}>
          pip install agent-papers-cli
        </div>

        <div style={{ fontSize: 16, color: "#a6e3a1", marginBottom: 24 }}>
          npx skills add collaborative-deep-research/agent-papers-cli
        </div>

        <div style={{ fontSize: 14, color: "#6c7086" }}>
          github.com/collaborative-deep-research/agent-papers-cli
        </div>
      </div>
    </AbsoluteFill>
  );
};
