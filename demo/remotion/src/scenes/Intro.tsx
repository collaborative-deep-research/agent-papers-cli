import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const titleY = spring({ frame, fps, config: { damping: 20 } }) * -20;

  const taglineOpacity = interpolate(frame, [30, 50], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#1e1e2e",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "monospace",
      }}
    >
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          fontSize: 48,
          fontWeight: "bold",
          color: "#cdd6f4",
          marginBottom: 24,
        }}
      >
        agent-papers-cli
      </div>
      <div
        style={{
          opacity: taglineOpacity,
          fontSize: 22,
          color: "#a6adc8",
          textAlign: "center",
          lineHeight: 1.6,
        }}
      >
        Building the infra for{" "}
        <span style={{ color: "#89b4fa", fontWeight: "bold" }}>
          Claude Code-native deep research
        </span>
      </div>
    </AbsoluteFill>
  );
};
