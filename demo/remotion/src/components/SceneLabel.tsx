import { useCurrentFrame, interpolate } from "remotion";

interface SceneLabelProps {
  step: number;
  text: string;
}

export const SceneLabel: React.FC<SceneLabelProps> = ({ step, text }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10, 20], [0, 0.95, 0.88], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 44,
        right: 24,
        opacity,
        backgroundColor: "rgba(255, 255, 255, 0.92)",
        padding: "8px 16px",
        borderRadius: 8,
        border: "1px solid rgba(232, 135, 54, 0.4)",
        fontFamily: "monospace",
        fontSize: 18,
        color: "#d9730d",
        fontWeight: "bold",
        letterSpacing: 0.3,
      }}
    >
      {step}. {text}
    </div>
  );
};
