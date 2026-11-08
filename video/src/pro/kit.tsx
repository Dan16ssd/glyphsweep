// "Technical brief" design kit for the 3-minute professional cut.
import React, { useMemo } from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont as loadPlex } from '@remotion/google-fonts/IBMPlexSans';
import { loadFont as loadMono } from '@remotion/google-fonts/IBMPlexMono';
import type { Caption } from '@remotion/captions';
import tlJson from '../../public/timeline_pro.json';
import capJson from '../../public/captions_pro.json';

export const P = {
  bg: '#090B10', bg2: '#0E1219', panel: '#121821', line: '#232C3A', line2: '#2E3A4C',
  ink: '#E9EDF3', mute: '#8A95A6', dim: '#566173',
  amber: '#F2B544', pass: '#3DDC97', fail: '#FF5C6C', blue: '#6CB4FF', violet: '#A78BFA',
};
export const PF = {
  sans: loadPlex('normal', { weights: ['300', '400', '500', '600', '700'], subsets: ['latin'] }).fontFamily,
  mono: loadMono('normal', { weights: ['400', '500', '600'], subsets: ['latin'] }).fontFamily,
};
export const FPS = 30;
export const TL = tlJson as { total: number; scenes: { id: string; start: number; duration: number; voice: number }[] };
export const CAPS = capJson as Caption[];
export const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

export const sceneOf = (id: string) => {
  const s = TL.scenes.find((x) => x.id === id);
  if (!s) throw new Error('no scene ' + id);
  return s;
};
// frame (relative to scene start) where a word matching re is spoken
export function cue(id: string, re: RegExp, fb = 0, nth = 0) {
  const s = sceneOf(id);
  const hits = CAPS.filter((w) => w.startMs >= s.start * 1000 && w.startMs < (s.start + s.duration) * 1000 && re.test(w.text.trim()));
  const h = hits[nth];
  return Math.round(((h ? h.startMs - s.start * 1000 : fb * 1000) / 1000) * FPS);
}
export const ease = (f: number, at: number, fps = FPS) => spring({ frame: f - at, fps, config: { damping: 200, stiffness: 120, mass: 0.8 } });
export const fade = (f: number, at: number, len = 14) => interpolate(f, [at, at + len], [0, 1], clamp);

export const Grid: React.FC = () => (
  <AbsoluteFill style={{ background: P.bg }}>
    <AbsoluteFill style={{
      backgroundImage: `linear-gradient(${P.line}55 1px, transparent 1px), linear-gradient(90deg, ${P.line}55 1px, transparent 1px)`,
      backgroundSize: '48px 48px', maskImage: 'radial-gradient(ellipse at 50% 45%, black 30%, transparent 85%)',
      WebkitMaskImage: 'radial-gradient(ellipse at 50% 45%, black 30%, transparent 85%)' }} />
  </AbsoluteFill>
);

// Running header: like a paper / lab report.
export const Header: React.FC<{ n: number; title: string }> = ({ n, title }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: 'absolute', left: 96, right: 96, top: 44, display: 'flex', justifyContent: 'space-between', fontFamily: PF.mono, fontSize: 19,
      color: P.dim, letterSpacing: 1.5, opacity: fade(f, 0, 10), borderBottom: `1px solid ${P.line}`, paddingBottom: 12 }}>
      <span><span style={{ color: P.amber }}>GLYPHSWEEP</span> · TECHNICAL BRIEF</span>
      <span>§{String(n).padStart(2, '0')} · {title.toUpperCase()}</span>
    </div>
  );
};

export const Fig: React.FC<{ n: string; children: React.ReactNode; x: number; y: number; w?: number; at?: number }> = ({ n, children, x, y: _y, w: _w, at = 0 }) => {
  const y = 918, w = 1728;
  const f = useCurrentFrame();
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, fontFamily: PF.mono, fontSize: 18, color: P.mute, opacity: fade(f, at) }}>
      <span style={{ color: P.ink }}>Fig. {n}</span> — {children}
    </div>
  );
};

export const H: React.FC<{ children: React.ReactNode; x?: number; y?: number; w?: number; size?: number; at?: number }> = ({ children, x = 96, y = 110, w = 1500, size = 60, at = 2 }) => {
  const f = useCurrentFrame();
  const e = ease(f, at);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, fontFamily: PF.sans, fontWeight: 600, fontSize: size, lineHeight: 1.1, color: P.ink,
      letterSpacing: -1, opacity: e, transform: `translateY(${(1 - e) * 18}px)` }}>{children}</div>
  );
};

export const Tag: React.FC<{ children: React.ReactNode; color?: string; style?: React.CSSProperties }> = ({ children, color = P.amber, style }) => (
  <span style={{ fontFamily: PF.mono, fontSize: 17, letterSpacing: 1.5, color, border: `1px solid ${color}`, borderRadius: 4, padding: '3px 8px',
    textTransform: 'uppercase', whiteSpace: 'nowrap', ...style }}>{children}</span>
);

export const Live: React.FC<{ children: React.ReactNode; x: number; y: number; at?: number }> = ({ children, x, y, at = 0 }) => {
  const f = useCurrentFrame();
  const blink = 0.55 + 0.45 * Math.sin(f / 6);
  return (
    <div style={{ position: 'absolute', left: x, top: y, opacity: fade(f, at), fontFamily: PF.mono, fontSize: 18, color: P.fail, letterSpacing: 1 }}>
      <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 5, background: P.fail, opacity: blink, marginRight: 10 }} />{children}
    </div>
  );
};

type Page = { startMs: number; endMs: number; tokens: { text: string; fromMs: number; toMs: number }[] };
export const ProCaptions = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const pages = useMemo(() => {
    const out: Page[] = [];
    let cur: Caption[] = [];
    const flush = () => { if (cur.length) out.push({ startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs, tokens: cur.map((w) => ({ text: w.text, fromMs: w.startMs, toMs: w.endMs })) }); cur = []; };
    for (const w of CAPS) { cur.push(w); const t = w.text.trim(); if (/[.?!:]$/.test(t) || cur.length >= 10 || (t.endsWith(',') && cur.length >= 5)) flush(); }
    flush();
    return out;
  }, []);
  const idx = pages.findIndex((p, i) => ms >= p.startMs && ms < Math.min(p.endMs + 500, pages[i + 1]?.startMs ?? Infinity));
  const page = pages[idx];
  if (!page) return null;
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 30 }}>
      <div style={{ maxWidth: 1500, background: 'rgba(9,11,16,.9)', borderTop: `1px solid ${P.line2}`, padding: '8px 22px', fontFamily: PF.sans, fontWeight: 500,
        fontSize: 33, lineHeight: 1.3, textAlign: 'center', color: P.ink, whiteSpace: 'pre-wrap' }}>
        {page.tokens.map((t, i) => <span key={i} style={{ color: ms >= t.fromMs && ms < t.toMs ? P.amber : ms >= t.toMs ? P.ink : P.dim }}>{t.text}</span>)}
      </div>
    </AbsoluteFill>
  );
};
