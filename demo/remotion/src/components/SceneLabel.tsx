import { useCurrentFrame, interpolate } from "remotion";

interface SceneLabelProps {
  text: string;
}

export const SceneLabel: React.FC<SceneLabelProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10, 20], [0, 0.9, 0.7], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 16,
        right: 16,
        opacity,
        backgroundColor: "rgba(30, 30, 46, 0.85)",
        padding: "8px 16px",
        borderRadius: 6,
        border: "1px solid rgba(137, 180, 250, 0.3)",
        fontFamily: "monospace",
        fontSize: 14,
        color: "#89b4fa",
        fontWeight: "bold",
      }}
    >
      {text}
    </div>
  );
};
