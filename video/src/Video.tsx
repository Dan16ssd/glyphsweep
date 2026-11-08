import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { C, FPS, timeline } from './theme';
import { Captions } from './Captions';
import { Story, Problem, Agent, Sandbox, Demo, Findings, Proof, Trust, Approve, Close } from './scenes';

const SCENES: Record<string, React.FC> = {
  '01-story': Story, '02-problem': Problem, '03-agent': Agent, '04-sandbox': Sandbox,
  '05-demo': Demo, '06-findings': Findings, '07-proof': Proof, '08-trust': Trust, '085-approve': Approve, '09-close': Close,
};

const Fade: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(frame, [0, 8, durationInFrames - 8, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

const Progress = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return <div style={{ position: 'absolute', top: 0, left: 0, height: 5, width: `${(frame / durationInFrames) * 100}%`, background: C.gold }} />;
};

export const GlyphSweep = () => (
  <AbsoluteFill style={{ background: C.deep }}>
    <Audio src={staticFile('narration.wav')} />
    {timeline.scenes.map((s) => {
      const Scene = SCENES[s.id];
      return (
        <Sequence key={s.id} from={Math.round(s.start * FPS)} durationInFrames={Math.round(s.duration * FPS)} name={s.id}>
          <Fade><Scene /></Fade>
        </Sequence>
      );
    })}
    <Captions />
    <Progress />
  </AbsoluteFill>
);
