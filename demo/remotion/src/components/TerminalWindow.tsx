import { useCurrentFrame, interpolate } from "remotion";

interface TerminalWindowProps {
  title?: string;
  children: React.ReactNode;
}

export const TerminalWindow: React.FC<TerminalWindowProps> = ({
  title = "Terminal",
  children,
}) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(frame, [0, 20], [0.985, 1.0], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "24px 40px 36px 40px",
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          borderRadius: 10,
          overflow: "hidden",
          boxShadow: "0 8px 32px rgba(46, 52, 64, 0.18), 0 2px 8px rgba(46, 52, 64, 0.08)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Title bar */}
        <div
          style={{
            height: 36,
            backgroundColor: "#d8dee9",
            display: "flex",
            alignItems: "center",
            paddingLeft: 14,
            paddingRight: 14,
            flexShrink: 0,
          }}
        >
          {/* Traffic light dots */}
          <div style={{ display: "flex", gap: 7 }}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#bf616a",
              }}
            />
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#ebcb8b",
              }}
            />
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#a3be8c",
              }}
            />
          </div>

          {/* Title */}
          <div
            style={{
              flex: 1,
              textAlign: "center",
              fontFamily: "monospace",
              fontSize: 12,
              color: "#4c566a",
              fontWeight: 500,
            }}
          >
            {title}
          </div>

          {/* Spacer to balance dots */}
          <div style={{ width: 55 }} />
        </div>

        {/* Content area */}
        <div
          style={{
            flex: 1,
            overflow: "hidden",
            position: "relative",
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};
