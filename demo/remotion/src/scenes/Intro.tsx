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
        backgroundColor: "#eceff4",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "monospace",
      }}
    >
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          fontSize: 56,
          fontWeight: "bold",
          color: "#2e3440",
          marginBottom: 24,
        }}
      >
        agent-papers-cli
      </div>
      <div
        style={{
          opacity: taglineOpacity,
          fontSize: 28,
          color: "#4c566a",
          textAlign: "center",
          lineHeight: 1.6,
        }}
      >
        Building the infra for{" "}
        <span style={{ color: "#5e81ac", fontWeight: "bold" }}>
          Claude Code-native deep research
        </span>
      </div>
    </AbsoluteFill>
  );
};
