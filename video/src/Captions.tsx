import { useMemo } from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import type { Caption } from '@remotion/captions';
import { C, F, captions } from './theme';

type Page = { startMs: number; endMs: number; tokens: { text: string; fromMs: number; toMs: number }[] };

function toPages(words: Caption[], max: number): Page[] {
  const pages: Page[] = [];
  let cur: Caption[] = [];
  const flush = () => {
    if (!cur.length) return;
    pages.push({ startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs, tokens: cur.map((w) => ({ text: w.text, fromMs: w.startMs, toMs: w.endMs })) });
    cur = [];
  };
  for (const w of words) {
    cur.push(w);
    const t = w.text.trim();
    if (/[.?!]$/.test(t) || cur.length >= max || (t.endsWith(',') && cur.length >= 5)) flush();
  }
  flush();
  return pages;
}

export const Captions = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const pages = useMemo(() => toPages(captions, 9), []);
  const idx = pages.findIndex((p, i) => ms >= p.startMs && ms < Math.min(p.endMs + 600, pages[i + 1]?.startMs ?? Infinity));
  const page = pages[idx];
  if (!page) return null;
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 34 }}>
      <div style={{ maxWidth: 1560, background: 'rgba(10, 9, 32, 0.88)', border: `1px solid ${C.line}`, borderRadius: 14, padding: '10px 26px',
        fontFamily: F.body, fontWeight: 600, fontSize: 38, lineHeight: 1.3, textAlign: 'center', color: C.ink, whiteSpace: 'pre-wrap' }}>
        {page.tokens.map((t, i) => {
          const active = ms >= t.fromMs && ms < t.toMs;
          const spoken = ms >= t.toMs;
          return <span key={i} style={{ color: active ? C.gold : spoken ? C.ink : '#9C98BE' }}>{t.text}</span>;
        })}
      </div>
    </AbsoluteFill>
  );
};
