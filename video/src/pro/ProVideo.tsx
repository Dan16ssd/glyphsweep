import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { FPS, P, ProCaptions, TL, clamp } from './kit';
import { Agent, Ceiling, Hook, Measure, Real } from './scenesA';
import { Approve, Arch, Business, Close, Hostile, RedTeam } from './scenesB';

const SCENES: Record<string, React.FC> = {
  'p01-hook': Hook, 'p02-measure': Measure, 'p03-agent': Agent, 'p04-real': Real, 'p05-ceiling': Ceiling, 'p06-arch': Arch,
  'p07-hostile': Hostile, 'p08-redteam': RedTeam, 'p09-approve': Approve, 'p10-business': Business, 'p11-close': Close,
};

// short cross-fade at each cut
const Fader: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, dur - 6, dur], [0, 1, 1, 0.0], clamp);
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

const Progress = () => {
  const f = useCurrentFrame();
  return <div style={{ position: 'absolute', left: 0, bottom: 0, height: 3, width: `${(f / (TL.total * FPS)) * 100}%`, background: P.amber, opacity: 0.8 }} />;
};

export const ProVideo = () => (
  <AbsoluteFill style={{ background: P.bg }}>
    <Audio src={staticFile('narration_pro.wav')} />
    {TL.scenes.map((s) => {
      const Comp = SCENES[s.id];
      const dur = Math.round(s.duration * FPS);
      return (
        <Sequence key={s.id} from={Math.round(s.start * FPS)} durationInFrames={dur} name={s.id}>
          <Fader dur={dur}><Comp /></Fader>
        </Sequence>
      );
    })}
    <ProCaptions />
    <Progress />
  </AbsoluteFill>
);
