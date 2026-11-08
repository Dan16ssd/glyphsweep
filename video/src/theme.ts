import { loadFont as loadJakarta } from '@remotion/google-fonts/PlusJakartaSans';
import { loadFont as loadLao } from '@remotion/google-fonts/NotoSansLao';
import { loadFont as loadThai } from '@remotion/google-fonts/NotoSansThai';
import { loadFont as loadKhmer } from '@remotion/google-fonts/NotoSansKhmer';
import { loadFont as loadMyanmar } from '@remotion/google-fonts/NotoSansMyanmar';
import { interpolate, spring } from 'remotion';
import timelineJson from '../public/timeline.json';
import captionsJson from '../public/captions.json';
import clipsJson from '../public/clips.json';
import type { Caption } from '@remotion/captions';

// Same palette as the live site and the deck.
export const C = {
  bg: '#14123A',
  deep: '#0F0D2E',
  panel: '#221F55',
  line: '#3A3680',
  ink: '#F4EFE2',
  muted: '#BDB8D8',
  gold: '#E8B54A',
  teal: '#4FD1B5',
  bad: '#FB7185',
  skin: '#D9A27A',
  hair: '#2A1C1A',
};

export const F = {
  body: loadJakarta('normal', { weights: ['400', '600', '700', '800'], subsets: ['latin'] }).fontFamily,
  lao: loadLao('normal', { weights: ['400', '700'] }).fontFamily,
  thai: loadThai('normal', { weights: ['400', '700'] }).fontFamily,
  khmer: loadKhmer('normal', { weights: ['400', '700'] }).fontFamily,
  myanmar: loadMyanmar('normal', { weights: ['400', '700'] }).fontFamily,
};

export const FPS = 30;
export const timeline = timelineJson as { total: number; scenes: { id: string; start: number; duration: number; voice: number }[] };
export const captions = captionsJson as Caption[];
export type ClipSeg = { at: number; dur: number; speed: number; label: string };
export const clips = clipsJson as Record<string, { segs: ClipSeg[]; facts: Record<string, string> }>;

export const scene = (id: string) => {
  const s = timeline.scenes.find((x) => x.id === id);
  if (!s) throw new Error(`no scene ${id}`);
  return s;
};

// Frame (relative to scene start) at which a word matching `re` is spoken in that scene.
export function cue(sceneId: string, re: RegExp, fallback = 0, nth = 0): number {
  const s = scene(sceneId);
  const from = s.start * 1000;
  const to = (s.start + s.duration) * 1000;
  const hits = captions.filter((w) => w.startMs >= from && w.startMs < to && re.test(w.text.trim()));
  const hit = hits[nth];
  return Math.round(((hit ? hit.startMs - from : fallback * 1000) / 1000) * FPS);
}

export const pop = (frame: number, at: number, fps = FPS) =>
  spring({ frame: frame - at, fps, config: { damping: 16, stiffness: 140, mass: 0.7 } });

export const fade = (frame: number, at: number, len = 12) =>
  interpolate(frame, [at, at + len], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
