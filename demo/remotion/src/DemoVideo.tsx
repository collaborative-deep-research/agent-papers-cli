import { AbsoluteFill, Sequence, OffthreadVideo, staticFile } from "remotion";
import { Intro } from "./scenes/Intro";
import { SceneLabel } from "./components/SceneLabel";
import { Transition } from "./scenes/Transition";
import { Outro } from "./scenes/Outro";

export const DEMO_FPS = 30;
export const DEMO_WIDTH = 1200;
export const DEMO_HEIGHT = 700;

/**
 * Full demo video composition.
 *
 * Timeline (approximate, in seconds):
 *   0-4    Intro — title + tagline
 *   4-13   Scene 1: Navigate a paper (outline, read section)
 *   13-20  Scene 2: Search within a paper (search, goto citation)
 *   20-29  Scene 3: Search the literature (semantic scholar, google scholar)
 *   29-32  Transition — "Now let your agent do it."
 *   32-62  Act 2: Claude Code deep research
 *   62-67  Outro — install command + GitHub
 *
 * Clip files (place in public/):
 *   - cli-features.mp4  (from: vhs demo/full-demo.tape)
 *   - claude-code.mp4   (from: vhs demo/claude-code-demo.tape or real recording)
 */
export const DemoVideo: React.FC = () => {
  const s = (sec: number) => sec * DEMO_FPS; // seconds to frames

  return (
    <AbsoluteFill style={{ backgroundColor: "#1e1e2e" }}>
      {/* === Intro === */}
      <Sequence from={0} durationInFrames={s(4)}>
        <Intro />
      </Sequence>

      {/* === Act 1: CLI Features (~25s) === */}
      <Sequence from={s(4)} durationInFrames={s(25)}>
        <AbsoluteFill>
          <OffthreadVideo src={staticFile("cli-features.mp4")} />

          {/* Scene labels overlay */}
          <Sequence from={0} durationInFrames={s(9)}>
            <SceneLabel text="Navigate a paper" />
          </Sequence>
          <Sequence from={s(9)} durationInFrames={s(7)}>
            <SceneLabel text="Search within a paper" />
          </Sequence>
          <Sequence from={s(16)} durationInFrames={s(9)}>
            <SceneLabel text="Search the literature" />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* === Transition === */}
      <Sequence from={s(29)} durationInFrames={s(3)}>
        <Transition />
      </Sequence>

      {/* === Act 2: Claude Code === */}
      <Sequence from={s(32)} durationInFrames={s(30)}>
        <AbsoluteFill>
          <OffthreadVideo src={staticFile("claude-code.mp4")} />
          <Sequence from={0} durationInFrames={s(30)}>
            <SceneLabel text="Deep research with Claude Code" />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* === Outro === */}
      <Sequence from={s(62)} durationInFrames={s(5)}>
        <Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
