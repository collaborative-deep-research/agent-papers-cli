import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

export const Transition: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15, 75, 90], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

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
      <div
        style={{
          fontSize: 36,
          color: "#cdd6f4",
          textAlign: "center",
          lineHeight: 1.6,
        }}
      >
        Now let your{" "}
        <span style={{ color: "#a6e3a1", fontWeight: "bold" }}>agent</span>{" "}
        do it.
      </div>
    </AbsoluteFill>
  );
};
