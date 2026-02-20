import { Composition } from "remotion";
import { DemoVideo, DEMO_FPS } from "./DemoVideo";

const DURATION = DEMO_FPS * 82; // ~82 seconds

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={DURATION}
        fps={DEMO_FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="DemoVideo720p"
        component={DemoVideo}
        durationInFrames={DURATION}
        fps={DEMO_FPS}
        width={1280}
        height={720}
      />
    </>
  );
};
