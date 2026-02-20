import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface Section {
  label: string;
  startSec: number;
  endSec: number;
}

const SECTIONS: Section[] = [
  { label: "CLI Demo", startSec: 0, endSec: 42 },
  { label: "Application: Deep Research in Claude Code", startSec: 42, endSec: 82 },
];

export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const currentSec = frame / fps;
  const totalSec = durationInFrames / fps;

  const opacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: 24,
        display: "flex",
        opacity,
        backgroundColor: "rgba(236, 239, 244, 0.85)",
      }}
    >
      {SECTIONS.map((section) => {
        const widthPct = ((section.endSec - section.startSec) / totalSec) * 100;
        const isActive = currentSec >= section.startSec && currentSec < section.endSec;
        const isPast = currentSec >= section.endSec;

        const sectionProgress = isActive
          ? (currentSec - section.startSec) / (section.endSec - section.startSec)
          : isPast
            ? 1
            : 0;

        const fillPct = sectionProgress * 100;

        return (
          <div
            key={section.startSec}
            style={{
              width: `${widthPct}%`,
              position: "relative",
              borderRight: "1px solid rgba(76, 86, 106, 0.15)",
              overflow: "hidden",
            }}
          >
            {/* Filled portion */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                bottom: 0,
                width: `${fillPct}%`,
                backgroundColor: isActive ? "#5e81ac" : "rgba(94, 129, 172, 0.3)",
              }}
            />

            {/* Dark label (visible on unfilled area) */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "monospace",
                fontSize: 10,
                fontWeight: isActive ? "bold" : "normal",
                color: "#4c566a",
                letterSpacing: 0.3,
                clipPath: `inset(0 0 0 ${fillPct}%)`,
              }}
            >
              {section.label}
            </div>

            {/* Light label (visible on filled area) */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "monospace",
                fontSize: 10,
                fontWeight: isActive ? "bold" : "normal",
                color: "#eceff4",
                letterSpacing: 0.3,
                clipPath: `inset(0 ${100 - fillPct}% 0 0)`,
              }}
            >
              {section.label}
            </div>
          </div>
        );
      })}
    </div>
  );
};
