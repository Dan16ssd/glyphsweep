import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, F, cue, fade, pop } from './theme';

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

const Bg: React.FC = () => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse at 60% 35%, #2A2470 0%, ${C.bg} 55%, ${C.deep} 100%)` }} />
);

const Eyebrow: React.FC<{ children: React.ReactNode; x?: number; y?: number }> = ({ children, x = 110, y = 70 }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: 'absolute', left: x, top: y, opacity: fade(f, 0), fontFamily: F.body, fontWeight: 700, fontSize: 26, letterSpacing: 5,
      textTransform: 'uppercase', color: C.gold }}>{children}</div>
  );
};

// Animated line that draws itself from (x1,y1) to (x2,y2).
const Wire: React.FC<{ x1: number; y1: number; x2: number; y2: number; at: number; color: string; dashed?: boolean; label?: string; lx?: number; ly?: number }> =
  ({ x1, y1, x2, y2, at, color, dashed, label, lx, ly }) => {
    const f = useCurrentFrame();
    const k = interpolate(f, [at, at + 14], [0, 1], clamp);
    const len = Math.hypot(x2 - x1, y2 - y1);
    const flow = (f * 3) % 40;
    return (
      <>
        <svg width="1920" height="1080" style={{ position: 'absolute', left: 0, top: 0 }}>
          <defs>
            <marker id={`h${x1}${y1}${x2}`} markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill={color} />
            </marker>
          </defs>
          <line x1={x1} y1={y1} x2={x1 + (x2 - x1) * k} y2={y1 + (y2 - y1) * k} stroke={color} strokeWidth="4"
            strokeDasharray={dashed ? '14 10' : `${len}`} strokeDashoffset={dashed ? -flow : 0}
            markerEnd={k > 0.95 ? `url(#h${x1}${y1}${x2})` : undefined} opacity={k > 0 ? 1 : 0} />
        </svg>
        {label ? (
          <div style={{ position: 'absolute', left: lx, top: ly, opacity: fade(f, at + 10), fontFamily: F.body, fontSize: 22, fontWeight: 700, color,
            background: 'rgba(15,13,46,.9)', padding: '4px 10px', borderRadius: 8, whiteSpace: 'nowrap' }}>{label}</div>
        ) : null}
      </>
    );
  };

const Box: React.FC<{ x: number; y: number; w: number; at: number; color: string; title: string; sub: React.ReactNode }> = ({ x, y, w, at, color, title, sub }) => {
  const f = useCurrentFrame();
  const p = pop(f, at);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, opacity: p, transform: `translateY(${(1 - p) * 20}px)`, background: 'rgba(34,31,85,.95)',
      border: `2px solid ${color}`, borderRadius: 20, padding: '18px 22px', fontFamily: F.body, color: C.ink, boxShadow: '0 16px 50px rgba(0,0,0,.4)' }}>
      <div style={{ fontSize: 30, fontWeight: 800, color }}>{title}</div>
      <div style={{ fontSize: 22, color: C.muted, marginTop: 6, lineHeight: 1.35 }}>{sub}</div>
    </div>
  );
};

// ---------- exploded view ----------
const LAYERS = [
  { name: 'Vultr Cloud Compute VM', sub: 'Singapore · runs everything below', color: '#4F8BD1', re: /Vultr/, fb: 3.9 },
  { name: 'Docker + gVisor runsc', sub: 'user-space kernel between page and host', color: '#7C6FE0', re: /gVisor/, fb: 9 },
  { name: 'Sandbox container', sub: 'read-only · non-root · no caps · 1.5 GB · 240 s', color: C.gold, re: /container/, fb: 9.7 },
  { name: 'Headless Chromium', sub: 'detectors · screenshots · bare-device OCR', color: C.teal, re: /headless/, fb: 10.5 },
  { name: 'The web page', sub: 'untrusted, maybe hostile', color: C.bad, re: /browser/, fb: 10.8 },
];

export const Exploded = () => {
  const f = useCurrentFrame();
  const id = '035-exploded';
  const at = LAYERS.map((l) => cue(id, l.re, l.fb));
  const explode = interpolate(f, [at[1] - 6, at[4] + 6], [0, 1], clamp);
  const gap = 34 + explode * 104;
  const cx = 900, base = 800, W = 250, Hh = 100, T = 18;
  const cp = cue(id, /control/, 2.2);
  const starts = cue(id, /starts/, 7.9);
  const proxy = cue(id, /proxy/, 13.1);
  const back = cue(id, /Screenshots/, 16.6);
  const inf = cue(id, /Serverless/, 21.7);
  const key = cue(id, /key/, 26.4);
  const ly = (i: number) => base - i * gap;
  return (
    <AbsoluteFill>
      <Bg />
      <Eyebrow>How it works · exploded view</Eyebrow>
      {/* the stack */}
      <svg width="1920" height="1080" style={{ position: 'absolute', left: 0, top: 0 }}>
        {LAYERS.map((l, i) => {
          const y = ly(i);
          const vis = i === 0 ? fade(f, at[0] - 4) : interpolate(f, [at[i] - 8, at[i] + 4], [0.25, 1], clamp);
          const top = `${cx},${y - Hh} ${cx + W},${y} ${cx},${y + Hh} ${cx - W},${y}`;
          const left = `${cx - W},${y} ${cx},${y + Hh} ${cx},${y + Hh + T} ${cx - W},${y + T}`;
          const right = `${cx},${y + Hh} ${cx + W},${y} ${cx + W},${y + T} ${cx},${y + Hh + T}`;
          return (
            <g key={l.name} opacity={vis}>
              <polygon points={left} fill={l.color} opacity="0.55" />
              <polygon points={right} fill={l.color} opacity="0.35" />
              <polygon points={top} fill="rgba(20,18,58,.92)" stroke={l.color} strokeWidth="3" />
              {i === 4 ? (
                // a tiny web page on the top plate
                <g transform={`translate(${cx},${y}) scale(1,0.5) rotate(45)`}>
                  <rect x="-120" y="-120" width="240" height="240" rx="12" fill="#FBF7EE" />
                  <rect x="-100" y="-100" width="120" height="16" rx="4" fill="#C98A4B" />
                  <rect x="-100" y="-70" width="200" height="70" rx="8" fill="#6B3E26" />
                  <rect x="-100" y="15" width="160" height="12" rx="4" fill="#B8AE98" />
                  <rect x="-100" y="40" width="120" height="12" rx="4" fill="#B8AE98" />
                  <rect x="-100" y="70" width="90" height="26" rx="6" fill="#FB7185" />
                </g>
              ) : (
                <g transform={`translate(${cx},${y}) scale(1,0.5) rotate(45)`} opacity="0.5">
                  {[-80, -40, 0, 40, 80].map((v) => <line key={v} x1="-110" y1={v} x2="110" y2={v} stroke={l.color} strokeWidth="2" />)}
                </g>
              )}
              {/* leader line to the label */}
              <line x1={cx + W} y1={y} x2={1230} y2={y} stroke={l.color} strokeWidth="2" strokeDasharray="4 6" opacity={fade(f, at[i])} />
            </g>
          );
        })}
      </svg>
      {LAYERS.map((l, i) => (
        <div key={l.name} style={{ position: 'absolute', left: 1240, top: ly(i) - 34, width: 620, opacity: fade(f, at[i]), fontFamily: F.body }}>
          <div style={{ fontSize: 30, fontWeight: 800, color: l.color }}>{l.name}</div>
          <div style={{ fontSize: 22, color: C.muted }}>{l.sub}</div>
        </div>
      ))}
      {/* side components */}
      <Box x={90} y={140} w={430} at={inf} color={C.teal} title="Vultr Serverless Inference" sub="qwen3.8-27b · plan · verify · fix" />
      <Box x={90} y={420} w={430} at={cp} color={C.gold} title="Control plane" sub={<>FastAPI on the VM · dispatches every stage<br />🔑 API key lives only here</>} />
      <Box x={90} y={730} w={430} at={proxy} color={C.teal} title="Allowlist proxy" sub="this job only: target site + Google Fonts" />
      <Wire x1={cx - W + 6} y1={ly(3)} x2={522} y2={445} at={back} color={C.ink} dashed label="screenshots · measurements · OCR" lx={552} ly={ly(3) - 70} />
      <Wire x1={522} y1={ly(2)} x2={cx - W - 6} y2={ly(2)} at={starts} color={C.gold} label="start a fresh sandbox" lx={530} ly={ly(2) - 46} />
      <Wire x1={cx - W + 60} y1={ly(2) + 50} x2={522} y2={770} at={proxy} color={C.teal} label="only way out" lx={540} ly={ly(2) + 90} />
      <Wire x1={300} y1={420} x2={300} y2={265} at={inf} color={C.teal} label="prompt + evidence" lx={315} ly={325} />
      {/* key never leaves */}
      <div style={{ position: 'absolute', left: cx - 50, top: ly(2) - 30, width: 270, textAlign: 'center', opacity: pop(f, key), fontFamily: F.body,
        fontSize: 28, fontWeight: 800, color: C.bad, background: 'rgba(15,13,46,.92)', border: `2px solid ${C.bad}`, borderRadius: 14, padding: '8px 0',
        transform: `scale(${0.8 + 0.2 * pop(f, key)})` }}>0 secrets inside</div>
    </AbsoluteFill>
  );
};

// ---------- business value ----------
const CUSTOMERS = [
  { ic: '🏦', t: 'Banks & telcos', s: 'apps used on budget Android phones', re: /Banks/, fb: 1.8 },
  { ic: '🛒', t: 'Online shops', s: 'checkout, prices, product names', re: /online/, fb: 2.8 },
  { ic: '🌐', t: 'Localization agencies', s: 'machine proof for every delivery', re: /Localization/, fb: 16.2 },
  { ic: '🏛', t: 'Government portals', s: 'accessibility + lang compliance', re: /government/, fb: 20.3 },
];

const NEXT = [
  { w: 'हिन्दी', font: () => F.deva, n: 'Hindi', re: /Hindi/, fb: 26.5 },
  { w: 'العربية', font: () => F.arabic, n: 'Arabic', re: /Arabic/, fb: 26.8 },
  { w: 'བོད་ཡིག', font: () => F.tibetan, n: 'Tibetan', re: /Tibetan/, fb: 28.1 },
  { w: 'සිංහල', font: () => F.sinhala, n: 'Sinhala', re: /Sinhala/, fb: 28.5 },
];

export const Business = () => {
  const f = useCurrentFrame();
  const id = '087-business';
  const broken = cue(id, /broken/, 7.3);
  const gate = cue(id, /release/, 12.3);
  const sold = cue(id, /sold/, 14);
  const ext = cue(id, /Unicode/, 23.4);
  const zoom = interpolate(f, [0, 960], [1.05, 1.15], clamp);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `scale(${zoom})` }}>
        <Img src={staticFile('slide-map.jpg')} style={{ width: 1920, height: 1080, objectFit: 'cover', opacity: 0.55 }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: 'linear-gradient(90deg, rgba(15,13,46,.97) 0%, rgba(15,13,46,.88) 55%, rgba(15,13,46,.35) 100%)' }} />
      <Eyebrow>Business value</Eyebrow>
      <div style={{ position: 'absolute', left: 110, top: 116, width: 1200, opacity: pop(f, 3), fontFamily: F.body, fontWeight: 800, fontSize: 60,
        color: C.ink, lineHeight: 1.08, letterSpacing: -1 }}>A release gate for the checkout people actually see</div>
      {/* customers */}
      <div style={{ position: 'absolute', left: 110, top: 300, width: 1240, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
        {CUSTOMERS.map((c) => {
          const a = cue(id, c.re, c.fb);
          const p = pop(f, a);
          return (
            <div key={c.t} style={{ opacity: p, transform: `translateY(${(1 - p) * 20}px)`, background: 'rgba(34,31,85,.92)', border: `1px solid ${C.line}`,
              borderRadius: 18, padding: '16px 22px', display: 'flex', gap: 18, alignItems: 'center', fontFamily: F.body }}>
              <div style={{ fontSize: 44 }}>{c.ic}</div>
              <div>
                <div style={{ fontSize: 30, fontWeight: 800, color: C.ink }}>{c.t}</div>
                <div style={{ fontSize: 22, color: C.muted }}>{c.s}</div>
              </div>
            </div>
          );
        })}
      </div>
      {/* pipeline */}
      <div style={{ position: 'absolute', left: 110, top: 560, display: 'flex', alignItems: 'center', gap: 18, opacity: fade(f, gate - 4), fontFamily: F.body }}>
        {[
          { t: 'git push', s: 'new release', c: C.muted },
          { t: 'GlyphSweep gate', s: 'audit · fix · prove · approve', c: C.gold },
          { t: 'deploy', s: 'only if it reads right', c: C.teal },
        ].map((s, i) => (
          <React.Fragment key={s.t}>
            {i > 0 ? <div style={{ fontSize: 44, color: C.muted, opacity: fade(f, gate + i * 8) }}>→</div> : null}
            <div style={{ opacity: fade(f, gate + i * 8), border: `2px solid ${s.c}`, borderRadius: 16, padding: '14px 22px', background: 'rgba(15,13,46,.9)',
              boxShadow: i === 1 ? `0 0 40px rgba(232,181,74,.25)` : 'none' }}>
              <div style={{ fontSize: 30, fontWeight: 800, color: s.c }}>{s.t}</div>
              <div style={{ fontSize: 22, color: C.muted }}>{s.s}</div>
            </div>
          </React.Fragment>
        ))}
        <div style={{ marginLeft: 12, opacity: pop(f, sold), transform: `rotate(-4deg) scale(${0.8 + 0.2 * pop(f, sold)})`, background: C.gold, color: C.bg,
          borderRadius: 14, padding: '12px 20px', fontSize: 28, fontWeight: 800 }}>per site / month</div>
      </div>
      {/* next scripts */}
      <div style={{ position: 'absolute', left: 110, top: 740, opacity: fade(f, ext), fontFamily: F.body }}>
        <div style={{ fontSize: 26, color: C.muted, fontWeight: 600 }}>Each new script = a Unicode range + two fonts. Next:</div>
        <div style={{ display: 'flex', gap: 18, marginTop: 14 }}>
          {NEXT.map((n) => {
            const p = pop(f, cue(id, n.re, n.fb));
            return (
              <div key={n.n} style={{ opacity: p, transform: `scale(${0.7 + 0.3 * p})`, border: `2px solid ${C.teal}`, borderRadius: 16, padding: '6px 22px',
                background: 'rgba(15,13,46,.9)', textAlign: 'center' }}>
                <div style={{ fontFamily: n.font(), fontSize: 42, color: C.ink, lineHeight: 1.5 }}>{n.w}</div>
                <div style={{ fontSize: 20, color: C.muted }}>{n.n}</div>
              </div>
            );
          })}
        </div>
      </div>
      {/* broken checkout on a phone */}
      <div style={{ position: 'absolute', left: 1450, top: 250, width: 330, opacity: fade(f, broken - 4), transform: `rotate(5deg) translateY(${(1 - pop(f, broken)) * 40}px)` }}>
        <div style={{ borderRadius: 40, background: '#0B0A1C', padding: 14, boxShadow: '0 30px 90px rgba(0,0,0,.6), 0 0 0 3px #2E2A66' }}>
          <div style={{ borderRadius: 28, background: '#FBF7EE', padding: '34px 20px 26px', fontFamily: F.body, color: '#2A1E14' }}>
            <div style={{ fontSize: 22, color: '#8A7F6A' }}>Checkout</div>
            <div style={{ height: 120, borderRadius: 14, background: 'linear-gradient(135deg,#6B3E26,#C98A4B)', margin: '12px 0' }} />
            <div style={{ display: 'flex', gap: 6, margin: '10px 0' }}>
              {Array.from({ length: 7 }).map((_, i) => <div key={i} style={{ width: 18, height: 26, border: '3px solid #8A86A8', borderRadius: 3 }} />)}
            </div>
            <div style={{ height: 64, borderRadius: 14, background: '#2A1E14', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              {Array.from({ length: 5 }).map((_, i) => <div key={i} style={{ width: 16, height: 24, border: '3px solid #C9C3E8', borderRadius: 3 }} />)}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 18, textAlign: 'center', fontFamily: F.body, fontSize: 28, fontWeight: 800, color: C.bad, opacity: fade(f, broken + 30) }}>
          = lost sales + support calls
        </div>
      </div>
    </AbsoluteFill>
  );
};
