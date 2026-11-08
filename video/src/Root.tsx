import { Composition } from 'remotion';
import { GlyphSweep } from './Video';
import { FPS, timeline } from './theme';

export const Root = () => (
  <Composition id="GlyphSweep" component={GlyphSweep} durationInFrames={Math.ceil(timeline.total * FPS)} fps={FPS} width={1920} height={1080} />
);
