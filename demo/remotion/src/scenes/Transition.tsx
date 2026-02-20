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
        backgroundColor: "#eceff4",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "monospace",
        opacity,
      }}
    >
      <div
        style={{
          fontSize: 44,
          color: "#2e3440",
          textAlign: "center",
          lineHeight: 1.6,
        }}
      >
        Now let your{" "}
        <span style={{ color: "#a3be8c", fontWeight: "bold" }}>agent</span>{" "}
        do it.
      </div>
    </AbsoluteFill>
  );
};
