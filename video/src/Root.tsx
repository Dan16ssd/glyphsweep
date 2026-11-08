import { Composition } from 'remotion';
import { GlyphSweep } from './Video';
import { FPS, timeline } from './theme';
import { ProVideo } from './pro/ProVideo';
import { TL } from './pro/kit';

export const Root = () => (
  <>
    <Composition id="GlyphSweep" component={GlyphSweep} durationInFrames={Math.ceil(timeline.total * FPS)} fps={FPS} width={1920} height={1080} />
    <Composition id="GlyphSweepPro" component={ProVideo} durationInFrames={Math.ceil(TL.total * FPS)} fps={FPS} width={1920} height={1080} />
  </>
);
