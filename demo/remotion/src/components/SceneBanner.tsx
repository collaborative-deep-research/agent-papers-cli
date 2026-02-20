import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

interface SceneBannerProps {
  step: number;
  text: string;
}

/**
 * Full-screen centered banner that fades in, holds, then dissolves.
 * Shown at the start of each scene for ~2 seconds.
 */
export const SceneBanner: React.FC<SceneBannerProps> = ({ step, text }) => {
  const frame = useCurrentFrame();

  // Timeline: fade in (0-12), hold (12-36), dissolve out (36-54)
  const opacity = interpolate(frame, [0, 12, 36, 54], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const scale = interpolate(frame, [0, 12, 36, 54], [0.92, 1, 1, 1.03], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: `rgba(46, 52, 64, ${opacity * 0.7})`,
        opacity: Math.min(opacity * 1.2, 1),
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          textAlign: "center",
          fontFamily: "monospace",
        }}
      >
        <div
          style={{
            fontSize: 20,
            color: "#d9730d",
            fontWeight: "bold",
            marginBottom: 12,
            letterSpacing: 2,
            textTransform: "uppercase",
            opacity,
          }}
        >
          Step {step}
        </div>
        <div
          style={{
            fontSize: 40,
            color: "#eceff4",
            fontWeight: "bold",
            opacity,
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
