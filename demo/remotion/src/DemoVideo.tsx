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
 *   4-12   Scene 1: Navigate a paper (outline, skim, read)
 *   12-19  Scene 2: Search & discover (search, goto citation, goto link)
 *   19-27  Scene 3: Search the literature (google, semantic scholar)
 *   27-34  Scene 4: Detect figures & tables
 *   34-40  Scene 5: Highlight & annotate
 *   40-43  Transition — "Now let your agent do it."
 *   43-73  Act 2: Claude Code deep research
 *   73-78  Outro — install command + GitHub
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

      {/* === Act 1: CLI Features === */}
      <Sequence from={s(4)} durationInFrames={s(36)}>
        <AbsoluteFill>
          <OffthreadVideo src={staticFile("cli-features.mp4")} />

          {/* Scene labels overlay */}
          <Sequence from={0} durationInFrames={s(8)}>
            <SceneLabel text="Navigate a paper" />
          </Sequence>
          <Sequence from={s(8)} durationInFrames={s(7)}>
            <SceneLabel text="Search & discover" />
          </Sequence>
          <Sequence from={s(15)} durationInFrames={s(8)}>
            <SceneLabel text="Search the literature" />
          </Sequence>
          <Sequence from={s(23)} durationInFrames={s(7)}>
            <SceneLabel text="Detect figures & tables" />
          </Sequence>
          <Sequence from={s(30)} durationInFrames={s(6)}>
            <SceneLabel text="Highlight & annotate" />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* === Transition === */}
      <Sequence from={s(40)} durationInFrames={s(3)}>
        <Transition />
      </Sequence>

      {/* === Act 2: Claude Code === */}
      <Sequence from={s(43)} durationInFrames={s(30)}>
        <AbsoluteFill>
          <OffthreadVideo src={staticFile("claude-code.mp4")} />
          <Sequence from={0} durationInFrames={s(30)}>
            <SceneLabel text="Deep research with Claude Code" />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* === Outro === */}
      <Sequence from={s(73)} durationInFrames={s(5)}>
        <Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
