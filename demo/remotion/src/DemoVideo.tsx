import {
  AbsoluteFill,
  Sequence,
  OffthreadVideo,
  staticFile,
} from "remotion";
import { Intro } from "./scenes/Intro";
import { SceneLabel } from "./components/SceneLabel";
import { SceneBanner } from "./components/SceneBanner";
import { ProgressBar } from "./components/ProgressBar";
import { TerminalWindow } from "./components/TerminalWindow";
import { Transition } from "./scenes/Transition";
import { Outro } from "./scenes/Outro";

export const DEMO_FPS = 30;
export const DEMO_WIDTH = 1920;
export const DEMO_HEIGHT = 1080;

/**
 * Full demo video composition.
 *
 * Timeline (seconds):
 *   0-4    Intro — title + tagline
 *   4-42   Act 1: CLI features (38s, clip is 37.6s)
 *            4-15   Scene 1: Navigate a paper
 *            15-25  Scene 2: Search within a paper
 *            25-42  Scene 3: Search the literature
 *   42-45  Transition — "Now let your agent do it."
 *   45-77  Act 2: Claude Code deep research (32s, clip is 32s)
 *   77-82  Outro — install command + GitHub
 *
 * Total: ~82s
 *
 * Each scene starts with a centered banner (~1.8s) that dissolves
 * into the terminal recording.
 */
export const DemoVideo: React.FC = () => {
  const s = (sec: number) => sec * DEMO_FPS;

  return (
    <AbsoluteFill style={{ backgroundColor: "#eceff4" }}>
      {/* === Intro === */}
      <Sequence from={0} durationInFrames={s(4)}>
        <Intro />
      </Sequence>

      {/* === Act 1: CLI Features (38s) === */}
      <Sequence from={s(4)} durationInFrames={s(38)}>
        <AbsoluteFill>
          <TerminalWindow title="agent-papers-cli">
            <OffthreadVideo
              src={staticFile("cli-features.mp4")}
              style={{ width: "100%", height: "100%", objectFit: "fill" }}
            />
          </TerminalWindow>

          {/* Scene banners (centered, dissolve) */}
          <Sequence from={0} durationInFrames={54}>
            <SceneBanner step={1} text="Navigate a paper" />
          </Sequence>
          <Sequence from={s(11)} durationInFrames={54}>
            <SceneBanner step={2} text="Search within a paper" />
          </Sequence>
          <Sequence from={s(21)} durationInFrames={54}>
            <SceneBanner step={3} text="Search the literature" />
          </Sequence>

          {/* Persistent scene labels (bottom-right, after banner dissolves) */}
          <Sequence from={54} durationInFrames={s(11) - 54}>
            <SceneLabel step={1} text="Navigate a paper" />
          </Sequence>
          <Sequence from={s(11) + 54} durationInFrames={s(10) - 54}>
            <SceneLabel step={2} text="Search within a paper" />
          </Sequence>
          <Sequence from={s(21) + 54} durationInFrames={s(17) - 54}>
            <SceneLabel step={3} text="Search the literature" />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* === Transition === */}
      <Sequence from={s(42)} durationInFrames={s(3)}>
        <Transition />
      </Sequence>

      {/* === Act 2: Claude Code === */}
      <Sequence from={s(45)} durationInFrames={s(32)}>
        <AbsoluteFill>
          <TerminalWindow title="Claude Code">
            <OffthreadVideo
              src={staticFile("claude-code.mp4")}
              style={{ width: "100%", height: "100%", objectFit: "fill" }}
            />
          </TerminalWindow>

          {/* Scene banner */}
          <Sequence from={0} durationInFrames={54}>
            <SceneBanner step={4} text="Deep research with Claude Code" />
          </Sequence>

          {/* Persistent label (after banner dissolves) */}
          <Sequence from={54} durationInFrames={s(32) - 54}>
            <SceneLabel step={4} text="Deep research with Claude Code" />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* === Outro === */}
      <Sequence from={s(77)} durationInFrames={s(5)}>
        <Outro />
      </Sequence>

      {/* === Progress bar (always visible) === */}
      <ProgressBar />
    </AbsoluteFill>
  );
};
