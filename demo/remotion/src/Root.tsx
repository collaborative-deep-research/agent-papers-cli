import { Composition } from "remotion";
import { DemoVideo, DEMO_FPS, DEMO_WIDTH, DEMO_HEIGHT } from "./DemoVideo";

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={DEMO_FPS * 82} // ~82 seconds
        fps={DEMO_FPS}
        width={DEMO_WIDTH}
        height={DEMO_HEIGHT}
      />
    </>
  );
};
