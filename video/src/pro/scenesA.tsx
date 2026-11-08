import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { F } from '../theme';
import lcJson from '../../public/laocoffee.json';
import { Fig, Grid, H, Header, Live, P, PF, Tag, clamp, cue, ease, fade } from './kit';

type Box = { x: number; y: number; w: number; h: number; cer: number };
const LC = lcJson as { id: string; url: string; score: { before: number; after: number }; ocr: { cer_before: number; cer_after: number }; sandboxes: number;
  blocked: number; lines: { dom: string; before: string; after: string }[]; boxes_before: Box[]; boxes_after: Box[];
  weights_before: Record<string, number>; weights_after: Record<string, number> };

// ---------------------------------------------------------------- §1 hook
export const Hook = () => {
  const f = useCurrentFrame();
  const id = 'p01-hook';
  const measured = cue(id, /measured/, 4);
  const half = cue(id, /Half/, 8);
  const n = Math.round(interpolate(f, [4, 50], [0, 150], clamp));
  const BAD = 73; // 51% of 144 sites with a visible rendering problem (research/RESULTS.md)
  const order = Array.from({ length: 144 }, (_, i) => (i * 61) % 144); // deterministic scatter
  const badSet = new Set(order.slice(0, BAD));
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={1} title="Problem" />
      <div style={{ position: 'absolute', left: 96, top: 170, fontFamily: PF.sans }}>
        <div style={{ fontSize: 30, color: P.mute, opacity: fade(f, 2) }}>Readers of Lao, Thai, Khmer and Burmese</div>
        <div style={{ fontSize: 190, fontWeight: 600, color: P.ink, letterSpacing: -6, lineHeight: 1, marginTop: 8, fontVariantNumeric: 'tabular-nums' }}>{n}M+</div>
        <div style={{ display: 'flex', gap: 26, marginTop: 34, opacity: fade(f, 20) }}>
          {[['ພາສາລາວ', F.lao], ['ภาษาไทย', F.thai], ['ភាសាខ្មែរ', F.khmer], ['မြန်မာ', F.myanmar]].map(([w, ff]) => (
            <span key={w} style={{ fontFamily: ff, fontSize: 40, color: P.mute }}>{w}</span>))}
        </div>
      </div>
      {/* 144-site matrix */}
      <div style={{ position: 'absolute', left: 1130, top: 190, opacity: fade(f, measured - 4) }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 44px)', gap: 12 }}>
          {Array.from({ length: 144 }).map((_, i) => {
            const bad = badSet.has(i);
            const t = half + order.indexOf(i) * 0.35;
            const on = bad ? fade(f, t, 6) : 0;
            const appear = fade(f, measured + (i % 12) * 1.2 + Math.floor(i / 12) * 0.8, 8);
            return <div key={i} style={{ width: 44, height: 44, borderRadius: 4, opacity: appear,
              background: on > 0 ? `rgba(255,92,108,${0.25 + 0.75 * on})` : '#1A212C', border: `1px solid ${on > 0.5 ? P.fail : P.line2}` }} />;
          })}
        </div>
        <div style={{ marginTop: 22, fontFamily: PF.mono, fontSize: 22, color: P.ink, opacity: fade(f, half) }}>
          <span style={{ color: P.fail }}>■</span> 73 / 144 = <b style={{ color: P.fail }}>51%</b> with a visible rendering defect
        </div>
      </div>
      <Fig n="1" x={1130} y={960} w={700} at={measured}>Live sites: government, banks, universities, telecoms, news. Desktop + phone width.</Fig>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §2 what breaks
const BARS = [
  { s: 'Burmese', v: 74, n: 19, w: 'မြန်မာ', ff: () => F.myanmar },
  { s: 'Khmer', v: 63, n: 19, w: 'ខ្មែរ', ff: () => F.khmer },
  { s: 'Lao', v: 50, n: 82, w: 'ລາວ', ff: () => F.lao },
  { s: 'Thai', v: 38, n: 24, w: 'ไทย', ff: () => F.thai },
];
export const Measure = () => {
  const f = useCurrentFrame();
  const id = 'p02-measure';
  const clip = cue(id, /clipped/, 1);
  const font = cue(id, /forty-five/, 3.5);
  const boxes = cue(id, /boxes/, 7.5);
  const qa = cue(id, /Latin/, 10);
  const word = 'ພາສາລາວ';
  const tofu = fade(f, boxes, 10);
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={2} title="What breaks" />
      <H>Defect rate by script</H>
      {/* bar chart */}
      <div style={{ position: 'absolute', left: 96, top: 230, width: 820 }}>
        {BARS.map((b, i) => {
          const e = ease(f, 6 + i * 6);
          return (
            <div key={b.s} style={{ display: 'grid', gridTemplateColumns: '170px 1fr 90px', alignItems: 'center', gap: 16, height: 86, borderBottom: `1px solid ${P.line}` }}>
              <div style={{ fontFamily: PF.sans, fontSize: 28, color: P.ink }}>{b.s} <span style={{ fontFamily: b.ff(), color: P.dim, fontSize: 24 }}>{b.w}</span></div>
              <div style={{ height: 30, background: '#161C26', position: 'relative' }}>
                <div style={{ position: 'absolute', inset: 0, width: `${b.v * e}%`, background: `linear-gradient(90deg, ${P.fail}88, ${P.fail})` }} />
              </div>
              <div style={{ fontFamily: PF.mono, fontSize: 26, color: P.ink, textAlign: 'right' }}>{Math.round(b.v * e)}%</div>
            </div>
          );
        })}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: PF.mono, fontSize: 16, color: P.dim, marginTop: 8, paddingLeft: 186, paddingRight: 106 }}>
          {[0, 25, 50, 75, 100].map((t) => <span key={t}>{t}</span>)}
        </div>
        <div style={{ display: 'flex', gap: 18, marginTop: 34, opacity: fade(f, font) }}>
          {[['45%', 'never send a font for their own script'], ['49%', 'declare the wrong lang']].map(([v, t]) => (
            <div key={v} style={{ flex: 1, border: `1px solid ${P.line2}`, padding: '14px 18px', background: P.panel }}>
              <div style={{ fontFamily: PF.mono, fontSize: 44, color: P.amber }}>{v}</div>
              <div style={{ fontFamily: PF.sans, fontSize: 21, color: P.mute }}>{t}</div>
            </div>))}
        </div>
      </div>
      {/* glyph anatomy */}
      <div style={{ position: 'absolute', left: 1040, top: 230, width: 780, height: 330, border: `1px solid ${P.line2}`, background: P.panel, opacity: fade(f, clip - 4), overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: 18, top: 12 }}><Tag color={P.fail}>clipped tone mark</Tag></div>
        <div style={{ position: 'absolute', left: 90, top: 70, width: 600, height: 170, overflow: 'hidden', borderTop: `2px dashed ${P.fail}` }}>
          <div style={{ fontFamily: F.lao, fontSize: 150, color: P.ink, lineHeight: 1, marginTop: -38 }}>ກີ້ ສູ້ ເຖິ</div>
        </div>
        <div style={{ position: 'absolute', left: 90, top: 70, width: 600, height: 1, background: P.fail }} />
        <div style={{ position: 'absolute', right: 22, top: 52, fontFamily: PF.mono, fontSize: 17, color: P.fail }}>clip box ↑ ink above it is lost</div>
        <div style={{ position: 'absolute', left: 18, bottom: 14, fontFamily: PF.mono, fontSize: 17, color: P.mute }}>detector: canvas actualBoundingBoxAscent vs overflow box</div>
      </div>
      <div style={{ position: 'absolute', left: 1040, top: 590, width: 780, height: 250, border: `1px solid ${P.line2}`, background: P.panel, opacity: fade(f, boxes - 6) }}>
        <div style={{ position: 'absolute', left: 18, top: 12 }}><Tag color={P.fail}>phone without the font</Tag></div>
        <div style={{ position: 'absolute', left: 60, top: 80, display: 'flex', gap: 10 }}>
          {Array.from(word).map((ch, i) => {
            const t = fade(f, boxes + i * 2, 6);
            return (
              <div key={i} style={{ width: 70, height: 100, position: 'relative' }}>
                <div style={{ position: 'absolute', inset: 0, fontFamily: F.lao, fontSize: 80, color: P.ink, opacity: 1 - t, textAlign: 'center' }}>{ch}</div>
                <div style={{ position: 'absolute', left: 12, top: 18, width: 46, height: 66, border: `4px solid ${P.mute}`, borderRadius: 3, opacity: t }} />
              </div>);
          })}
        </div>
        <div style={{ position: 'absolute', left: 18, bottom: 14, fontFamily: PF.mono, fontSize: 17, color: P.mute, opacity: tofu }}>“tofu”: the glyph is missing, not the text</div>
      </div>
      <div style={{ position: 'absolute', left: 1040, top: 870, width: 780, fontFamily: PF.sans, fontSize: 24, color: P.mute, opacity: fade(f, qa) }}>
        Latin-first QA tools check that text <i>exists</i>, not that a reader can <i>see</i> it.
      </div>
      <Fig n="2" x={96} y={960} w={900} at={6}>Share of sites with a visible defect, by script (n = 144). Source: research/RESULTS.md</Fig>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §3 the agent
const NODES = [
  { k: 'detect', t: 'Detectors', s: 'glyph ink, fonts, lang', re: /Detectors/, fb: 6, c: P.blue },
  { k: 'bare', t: 'Bare-phone render', s: 'no system font for the script', re: /bare-phone/, fb: 8.5, c: P.blue },
  { k: 'ocr', t: 'OCR', s: 'Tesseract → CER', re: /OCR/, fb: 10, c: P.blue },
  { k: 'plan', t: 'Plan', s: 'pick pages to audit', re: /plans/, fb: 13, c: P.amber },
  { k: 'vision', t: 'Vision verify', s: 'what a reader sees', re: /vision/, fb: 15.5, c: P.amber },
  { k: 'fix', t: 'Fix → prove', s: 'patch, re-measured fresh', re: /patch/, fb: 17.5, c: P.pass },
];
export const Agent = () => {
  const f = useCurrentFrame();
  const id = 'p03-agent';
  const formula = cue(id, /number/, 11);
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={3} title="Method" />
      <H>Find it. Fix it. <span style={{ color: P.pass }}>Prove it.</span></H>
      <div style={{ position: 'absolute', left: 96, top: 300, display: 'flex', alignItems: 'stretch', gap: 0 }}>
        {NODES.map((n, i) => {
          const at = cue(id, n.re, n.fb);
          const e = ease(f, at);
          return (
            <React.Fragment key={n.k}>
              {i > 0 ? <div style={{ width: 34, alignSelf: 'center', height: 2, background: f > at ? n.c : P.line2 }} /> : null}
              <div style={{ width: 252, padding: '18px 18px', border: `1.5px solid ${e > 0.5 ? n.c : P.line2}`, background: P.panel, opacity: 0.35 + 0.65 * e,
                transform: `translateY(${(1 - e) * 10}px)` }}>
                <div style={{ fontFamily: PF.mono, fontSize: 15, color: n.c, letterSpacing: 1.5 }}>{String(i + 1).padStart(2, '0')}</div>
                <div style={{ fontFamily: PF.sans, fontSize: 27, fontWeight: 600, color: P.ink, marginTop: 6 }}>{n.t}</div>
                <div style={{ fontFamily: PF.sans, fontSize: 19, color: P.mute, marginTop: 4 }}>{n.s}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: 96, top: 520, display: 'flex', gap: 12, opacity: fade(f, cue(id, /Vultr/, 1)) }}>
        <Tag color={P.blue}>sandbox · deterministic</Tag><Tag color={P.amber}>Vultr Serverless Inference · qwen3.8-27b</Tag><Tag color={P.pass}>fresh sandbox per proof</Tag>
      </div>
      {/* the metric */}
      <div style={{ position: 'absolute', left: 96, top: 590, width: 1728, height: 300, border: `1px solid ${P.line2}`, background: P.panel, opacity: fade(f, formula - 6),
        display: 'flex', alignItems: 'center', gap: 70, padding: '0 56px' }}>
        <div style={{ fontFamily: PF.mono, fontSize: 46, color: P.ink }}>
          CER = <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', verticalAlign: 'middle' }}>
            <span style={{ borderBottom: `2px solid ${P.ink}`, padding: '0 10px' }}>edit_distance(OCR, DOM)</span><span>|DOM|</span></span>
        </div>
        <div style={{ fontFamily: PF.sans, fontSize: 26, color: P.mute, lineHeight: 1.45, width: 640 }}>
          Render the page on a phone profile with <b style={{ color: P.ink }}>no font for the script</b>, OCR the pixels, compare with the text in the DOM.
          Tofu becomes a number. <span style={{ color: P.amber }}>0% = fully readable.</span>
        </div>
      </div>
      <Fig n="3" x={96} y={960} at={formula}>Pipeline. Blue runs in the sandbox, amber is the model, green is the proof.</Fig>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §4 real site
const CROP_Y = 380, SCALE = 0.6;
const Pane: React.FC<{ src: string; boxes: Box[]; color: string; label: string; at: number; x: number; scroll: number; showBoxes: number }> =
  ({ src, boxes, color, label, at, x, scroll, showBoxes }) => {
    const f = useCurrentFrame();
    const e = ease(f, at);
    return (
      <div style={{ position: 'absolute', left: x, top: 214, width: 800, opacity: e }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontFamily: PF.sans, fontSize: 25, fontWeight: 600, color }}>{label}</span>
        </div>
        <div style={{ height: 560, overflow: 'hidden', border: `1.5px solid ${color}`, background: '#fff', position: 'relative' }}>
          <div style={{ position: 'absolute', left: -10, top: -(CROP_Y * SCALE) - scroll, width: 1280 * SCALE }}>
            <Img src={staticFile(src)} style={{ width: 1280 * SCALE, display: 'block' }} />
            {boxes.slice(0, 6).map((b, i) => (
              <div key={i} style={{ position: 'absolute', left: b.x * SCALE - 4, top: b.y * SCALE - 4, width: b.w * SCALE + 8, height: b.h * SCALE + 8,
                border: `2px solid ${color}`, opacity: fade(f, showBoxes + i * 4, 6), background: `${color}14` }}>
                <span style={{ position: 'absolute', right: -2, top: -24, fontFamily: PF.mono, fontSize: 15, color: '#fff', background: color, padding: '1px 6px' }}>
                  CER {Math.round(b.cer * 100)}%</span>
              </div>))}
          </div>
        </div>
      </div>
    );
  };
export const Real = () => {
  const f = useCurrentFrame();
  const id = 'p04-real';
  const heading = cue(id, /heading/, 5);
  const after = cue(id, /proven/, 9);
  const err = cue(id, /ninety-four/, 12.5);
  const sc = cue(id, /fifty/, 15.5);
  const scroll = interpolate(f, [heading + 20, err + 30], [250, 560], clamp);
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={4} title="Result on a real site" />
      <div style={{ position: 'absolute', left: 96, top: 108, fontFamily: PF.sans, fontSize: 52, fontWeight: 600, color: P.ink, opacity: ease(f, 2) }}>
        laocoffee.org/lao/ <span style={{ fontSize: 30, color: P.mute, fontWeight: 400 }}> Keoset Community Coffee · Northern Laos</span></div>
      <Pane src="lc-before_bare.jpg" boxes={LC.boxes_before} color={P.fail} label="Bare phone · before" at={4} x={96} scroll={scroll} showBoxes={heading} />
      <Pane src="lc-after_r3_bare.jpg" boxes={LC.boxes_after} color={P.pass} label="Bare phone · proven patch" at={after} x={1024} scroll={scroll} showBoxes={after + 10} />
      <div style={{ position: 'absolute', left: 96, top: 840, display: 'flex', gap: 22 }}>
        {[
          { k: 'mean OCR error (CER)', a: `${Math.round(LC.ocr.cer_before * 100)}%`, b: `${Math.round(LC.ocr.cer_after * 100)}%`, at: err },
          { k: 'script readiness score', a: `${LC.score.before}`, b: `${LC.score.after}`, at: sc },
        ].map((m) => (
          <div key={m.k} style={{ opacity: fade(f, m.at - 4), border: `1px solid ${P.line2}`, background: P.panel, padding: '10px 22px', minWidth: 400 }}>
            <div style={{ fontFamily: PF.mono, fontSize: 17, color: P.mute }}>{m.k}</div>
            <div style={{ fontFamily: PF.mono, fontSize: 48, color: P.ink }}><span style={{ color: P.fail }}>{m.a}</span> → <span style={{ color: P.pass }}>{m.b}</span></div>
          </div>))}
        <div style={{ alignSelf: 'center', marginLeft: 20, fontFamily: PF.mono, fontSize: 18, color: P.mute, lineHeight: 1.6, opacity: fade(f, sc) }}>
          {LC.sandboxes} sandboxes · all destroyed<br />{LC.blocked} off-allowlist requests blocked<br />vision confirmed 11/12 defects
        </div>
      </div>
      <Live x={1360} y={124} at={6}>REAL SWEEP {LC.id}</Live>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §5 the 74 ceiling
const LABEL: Record<string, string> = { html_lang: 'wrong lang tag', untranslated: 'untranslated UI', tight_line_height: 'clipped / tight lines', font_fallback: 'no font for the script' };
export const Ceiling = () => {
  const f = useCurrentFrame();
  const id = 'p05-ceiling';
  const ceil = cue(id, /ceiling/, 2.5);
  const owner = cue(id, /owner/, 6);
  const wb = Object.entries(LC.weights_before).sort((a, b) => (a[0] in LC.weights_after ? -1 : 1) - (b[0] in LC.weights_after ? -1 : 1));
  const out = fade(f, ceil + 10, 20);
  const sum = interpolate(out, [0, 1], [28, 12]);
  const scoreNow = Math.round(100 * Math.exp(-sum / 40));
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={5} title="Why 74" />
      <H>Why does the score stop at <span style={{ color: P.amber }}>74</span>?</H>
      <div style={{ position: 'absolute', left: 96, top: 250, fontFamily: PF.mono, fontSize: 56, color: P.ink, opacity: fade(f, 6) }}>
        score = 100 · e<sup style={{ fontSize: 34 }}>−Σw / 40</sup>
        <span style={{ fontSize: 24, color: P.mute, marginLeft: 30 }}>w = worst severity per defect type (high 8 · medium 4)</span>
      </div>
      {/* weight bar */}
      <div style={{ position: 'absolute', left: 96, top: 420, width: 1400, height: 90, display: 'flex' }}>
        {wb.map(([k, w]) => {
          const css = !(k in LC.weights_after);
          const width = (w / 28) * 1400 * (css ? 1 - out : 1);
          if (css && out > 0.97) return null;
          return (
            <div key={k} style={{ width, height: 90, background: css ? `${P.blue}33` : `${P.amber}33`, border: `1.5px solid ${css ? P.blue : P.amber}`, overflow: 'hidden',
              transform: css ? `translateY(${out * 60}px)` : 'none', opacity: css ? 1 - out * 0.9 : 1, padding: '10px 14px', boxSizing: 'border-box' }}>
              <div style={{ fontFamily: PF.mono, fontSize: 18, color: css ? P.blue : P.amber, whiteSpace: 'nowrap' }}>{css ? 'CSS-fixable' : 'needs site owner'} · w={w}</div>
              <div style={{ fontFamily: PF.sans, fontSize: 22, color: P.ink, whiteSpace: 'nowrap' }}>{LABEL[k] ?? k}</div>
            </div>);
        })}
        <div style={{ marginLeft: 30, alignSelf: 'center', fontFamily: PF.mono, fontSize: 30, color: P.ink, whiteSpace: 'nowrap' }}>
          Σw = {Math.round(sum)} → <span style={{ fontSize: 64, color: out > 0.95 ? P.amber : P.ink }}>{scoreNow}</span></div>
      </div>
      <div style={{ position: 'absolute', left: 96, top: 640, width: 1700, display: 'flex', gap: 22, opacity: fade(f, owner - 4) }}>
        {[
          ['The patch removes', 'clipping and the missing font: everything CSS can change.', P.blue],
          ['Left for the site owner', 'lang="lo" in the HTML and translated menu text. GlyphSweep drafts the translations.', P.amber],
          ['Reported, not hidden', 'Every finding ends as fixed, open, or needs a source change.', P.pass],
        ].map(([t, s, c]) => (
          <div key={t} style={{ flex: 1, borderTop: `3px solid ${c}`, background: P.panel, padding: '18px 22px' }}>
            <div style={{ fontFamily: PF.sans, fontSize: 27, fontWeight: 600, color: P.ink }}>{t}</div>
            <div style={{ fontFamily: PF.sans, fontSize: 21, color: P.mute, marginTop: 6, lineHeight: 1.4 }}>{s}</div>
          </div>))}
      </div>
      <Fig n="5" x={96} y={960} at={ceil}>laocoffee.org: Σw 28 → 50 before, 12 → 74 after (8 + 4 left). Same formula as the 144-site study.</Fig>
    </AbsoluteFill>
  );
};
