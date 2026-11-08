import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, F, FPS, clips, cue, fade, pop } from './theme';

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// ---------- shared pieces ----------

const Backdrop: React.FC<{ tint?: string }> = ({ tint = C.bg }) => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse at 70% 30%, #2A2470 0%, ${tint} 55%, ${C.deep} 100%)` }}>
    <svg width="1920" height="1080" style={{ position: 'absolute', opacity: 0.08 }}>
      <defs>
        <pattern id="sinh" width="64" height="64" patternUnits="userSpaceOnUse">
          <path d="M32 4 L60 32 L32 60 L4 32 Z" fill="none" stroke={C.gold} strokeWidth="2" />
          <path d="M32 20 L44 32 L32 44 L20 32 Z" fill={C.gold} />
        </pattern>
      </defs>
      <rect x="0" y="1000" width="1920" height="80" fill="url(#sinh)" />
      <rect x="0" y="0" width="1920" height="40" fill="url(#sinh)" />
    </svg>
  </AbsoluteFill>
);

const Eyebrow: React.FC<{ children: React.ReactNode; at?: number; x?: number; y?: number }> = ({ children, at = 0, x = 120, y = 90 }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: 'absolute', left: x, top: y, opacity: fade(f, at), fontFamily: F.body, fontWeight: 700, fontSize: 26, letterSpacing: 5,
      textTransform: 'uppercase', color: C.gold }}>{children}</div>
  );
};

const Title: React.FC<{ children: React.ReactNode; at?: number; x?: number; y?: number; w?: number; size?: number }> = ({ children, at = 4, x = 120, y = 136, w = 1500, size = 64 }) => {
  const f = useCurrentFrame();
  const p = pop(f, at);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, opacity: p, transform: `translateY(${(1 - p) * 24}px)`, fontFamily: F.body,
      fontWeight: 800, fontSize: size, lineHeight: 1.08, color: C.ink, letterSpacing: -1 }}>{children}</div>
  );
};

// Flat 2D character. mood: 0 = confused, 1 = happy
const Noy: React.FC<{ mood: number; x: number; y: number; s?: number }> = ({ mood, x, y, s = 1 }) => {
  const f = useCurrentFrame();
  const breathe = Math.sin(f / 18) * 3;
  const blink = f % 110 < 4 ? 0.15 : 1;
  const mouth = interpolate(mood, [0, 1], [-10, 14]);
  return (
    <svg width={460 * s} height={620 * s} viewBox="0 0 460 620" style={{ position: 'absolute', left: x, top: y + breathe }}>
      {/* body */}
      <path d="M70 620 C70 470 130 410 230 410 C330 410 390 470 390 620 Z" fill={C.gold} />
      <path d="M190 410 L230 470 L270 410 Z" fill="#C8922E" />
      {/* sinh skirt band hint */}
      <rect x="70" y="580" width="320" height="40" fill="#8A2E3B" />
      <path d="M70 590 H390" stroke={C.gold} strokeWidth="4" strokeDasharray="14 10" />
      {/* neck + head */}
      <rect x="205" y="350" width="50" height="70" rx="20" fill={C.skin} />
      <path d="M110 230 C110 100 350 100 350 230 L350 330 C320 360 140 360 110 330 Z" fill={C.hair} />
      <ellipse cx="230" cy="250" rx="100" ry="118" fill={C.skin} />
      <path d="M128 215 C150 120 320 110 336 220 C300 170 200 160 128 215 Z" fill={C.hair} />
      {/* eyes */}
      <ellipse cx="192" cy="252" rx="10" ry={12 * blink} fill="#1A1430" />
      <ellipse cx="268" cy="252" rx="10" ry={12 * blink} fill="#1A1430" />
      {/* brows: worried when confused */}
      <path d={`M172 ${222 - mood * 6} L212 ${214 + (1 - mood) * 8}`} stroke="#1A1430" strokeWidth="6" strokeLinecap="round" />
      <path d={`M248 ${214 + (1 - mood) * 8} L288 ${222 - mood * 6}`} stroke="#1A1430" strokeWidth="6" strokeLinecap="round" />
      <path d={`M200 312 Q230 ${312 + mouth} 260 312`} stroke="#7A2E2E" strokeWidth="7" fill="none" strokeLinecap="round" />
      <ellipse cx="168" cy="292" rx="16" ry="9" fill="#E07A6A" opacity={0.35 + mood * 0.3} />
      <ellipse cx="292" cy="292" rx="16" ry="9" fill="#E07A6A" opacity={0.35 + mood * 0.3} />
      {/* arm raised holding phone (phone drawn separately) */}
      <path d="M360 470 C420 470 450 430 450 380" stroke={C.gold} strokeWidth="58" strokeLinecap="round" fill="none" />
      <circle cx="450" cy="372" r="30" fill={C.skin} />
    </svg>
  );
};

const Tofu: React.FC<{ n: number; size: number }> = ({ n, size }) => (
  <span>
    {Array.from({ length: n }).map((_, i) => (
      <span key={i} style={{ display: 'inline-block', width: size * 0.55, height: size * 0.85, border: `3px solid #8A86A8`, borderRadius: 3,
        marginRight: size * 0.08, verticalAlign: 'middle' }} />
    ))}
  </span>
);

// Phone with the Lao coffee shop. broken: 0..1
const Phone: React.FC<{ broken: number; x: number; y: number }> = ({ broken, x, y }) => {
  const f = useCurrentFrame();
  const line = (lao: string, n: number, size: number, weight = 400, clip = false) => (
    <div style={{ position: 'relative', height: size * 1.9, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, opacity: 1 - broken, fontFamily: F.lao, fontSize: size, fontWeight: weight, lineHeight: 1.9 }}>{lao}</div>
      <div style={{ position: 'absolute', inset: 0, opacity: broken, fontFamily: F.lao, fontSize: size, fontWeight: weight, lineHeight: 1.9 }}>
        {clip ? (
          <div style={{ height: size * 1.05, overflow: 'hidden', marginTop: size * 0.55, lineHeight: 1 }}>
            <div style={{ marginTop: -size * 0.12 }}>{lao}</div>
          </div>
        ) : <Tofu n={n} size={size} />}
      </div>
    </div>
  );
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: 430, height: 860, borderRadius: 56, background: '#0B0A1C', padding: 18,
      boxShadow: `0 40px 120px rgba(0,0,0,.55), 0 0 0 3px #2E2A66, 0 0 ${60 * (1 - broken)}px rgba(79,209,181,${0.35 * (1 - broken)})`,
      transform: `rotate(${-4 + Math.sin(f / 40) * 0.6}deg)` }}>
      <div style={{ width: '100%', height: '100%', borderRadius: 40, background: '#FBF7EE', overflow: 'hidden', color: '#2A1E14', padding: '54px 30px 0' }}>
        {line('ຮ້ານກາເຟດາວ', 6, 44, 700)}
        {line('ກາເຟລາວແທ້ ຈາກພູພຽງບໍລະເວນ', 11, 26, 400, true)}
        <div style={{ height: 210, borderRadius: 22, margin: '14px 0', background: 'linear-gradient(135deg,#6B3E26,#C98A4B)' }} />
        {line('ກາເຟອາຣາບິກາ ຄົ່ວອ່ອນ', 10, 30, 700)}
        {line('ລາຄາ 120,000 ກີບ', 7, 28, 400, true)}
        <div style={{ marginTop: 26, height: 84, borderRadius: 20, background: '#2A1E14', color: '#FBF7EE', display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontFamily: F.lao, fontSize: 34, fontWeight: 700 }}>
          {broken > 0.5 ? <Tofu n={5} size={34} /> : 'ຊຳລະເງິນ'}
        </div>
      </div>
    </div>
  );
};

const Badge: React.FC<{ children: React.ReactNode; color?: string; at: number; x?: number; y?: number; w?: number; flow?: boolean }> = ({ children, color = C.teal, at, x, y, w, flow }) => {
  const f = useCurrentFrame();
  const p = pop(f, at);
  return (
    <div style={{ position: flow ? 'relative' : 'absolute', left: flow ? undefined : x, top: flow ? undefined : y, width: w, opacity: p, transform: `translateX(${(1 - p) * 40}px)`, background: 'rgba(15,13,46,0.92)',
      border: `2px solid ${color}`, borderRadius: 16, padding: '14px 22px', fontFamily: F.body, fontWeight: 700, fontSize: 28, color: C.ink, lineHeight: 1.3,
      boxShadow: `0 10px 40px rgba(0,0,0,.4)` }}>{children}</div>
  );
};

// ---------- 01 story ----------
export const Story = () => {
  const f = useCurrentFrame();
  const broke = cue('01-story', /boxes/, 7);
  const devs = cue('01-story', /developers/, 12.5);
  const broken = interpolate(f, [broke - 20, broke + 4], [0, 1], clamp);
  const sky = interpolate(f, [0, 500], [0, -40], clamp);
  return (
    <AbsoluteFill>
      <Backdrop />
      {/* That Luang + skyline */}
      <svg width="1920" height="1080" style={{ position: 'absolute', transform: `translateX(${sky}px)` }}>
        {Array.from({ length: 60 }).map((_, i) => (
          <circle key={i} cx={(i * 337) % 1920} cy={(i * 131) % 600} r={(i % 3) + 1} fill="#fff" opacity={0.2 + 0.5 * Math.abs(Math.sin(f / 30 + i))} />
        ))}
        <g fill="#C99A3A" opacity="0.85">
          <path d="M210 960 L210 860 L260 860 L270 760 L290 640 L300 560 L310 640 L330 760 L340 860 L390 860 L390 960 Z" />
          <path d="M140 960 L160 900 L180 960 Z M420 960 L440 900 L460 960 Z M100 960 H500 V990 H100 Z" />
        </g>
        <path d="M0 990 Q480 930 960 975 T1920 960 V1080 H0 Z" fill="#1B1748" />
      </svg>
      <Eyebrow>Vientiane · 8:14 pm</Eyebrow>
      <Noy mood={0.7 - broken * 0.7} x={600} y={340} />
      <Phone broken={broken} x={1000} y={110} />
      <Badge at={broke + 6} x={1470} y={300} color={C.bad} w={360}>Empty boxes (tofu)</Badge>
      <Badge at={broke + 20} x={1470} y={400} color={C.bad} w={360}>Tone marks cut off</Badge>
      {/* developers' view */}
      <div style={{ position: 'absolute', left: 120, top: 200, width: 440, opacity: fade(f, devs), transform: `translateY(${(1 - pop(f, devs)) * 30}px)` }}>
        <div style={{ background: '#1E1B4B', border: `2px solid ${C.line}`, borderRadius: 18, padding: 22, fontFamily: F.body, color: C.ink }}>
          <div style={{ fontSize: 22, color: C.muted, marginBottom: 10 }}>Dev team laptop</div>
          <div style={{ fontSize: 30, fontWeight: 800, color: C.teal }}>✓ All tests passed</div>
          <div style={{ fontSize: 24, color: C.muted, marginTop: 8 }}>Screenshot diff: 0 px · Lint: OK</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------- 02 problem ----------
const SCRIPTS = [
  { word: 'ພາສາລາວ', font: () => F.lao, name: 'Lao', pct: 50 },
  { word: 'ภาษาไทย', font: () => F.thai, name: 'Thai', pct: 38 },
  { word: 'ភាសាខ្មែរ', font: () => F.khmer, name: 'Khmer', pct: 63 },
  { word: 'မြန်မာ', font: () => F.myanmar, name: 'Burmese', pct: 74 },
];

const Count: React.FC<{ to: number; at: number; suffix?: string; color: string; size: number }> = ({ to, at, suffix = '', color, size }) => {
  const f = useCurrentFrame();
  const v = Math.round(interpolate(f, [at, at + 24], [0, to], clamp));
  return <span style={{ fontFamily: F.body, fontWeight: 800, fontSize: size, color, opacity: fade(f, at, 6), lineHeight: 1 }}>{v}{suffix}</span>;
};

export const Problem = () => {
  const f = useCurrentFrame();
  const id = '02-problem';
  const scan = cue(id, /144/, 5.5);
  const s51 = cue(id, /51%/, 9);
  const s45 = cue(id, /45%/, 13);
  const burm = cue(id, /Burmese/, 18, 1);
  const visible = Math.round(144 * 0.51);
  return (
    <AbsoluteFill>
      <Backdrop />
      <Eyebrow>Not one website</Eyebrow>
      <div style={{ position: 'absolute', left: 120, top: 150, display: 'flex', gap: 56 }}>
        {SCRIPTS.map((s, i) => {
          const p = pop(f, 6 + i * 8);
          return (
            <div key={s.name} style={{ opacity: p, transform: `translateY(${(1 - p) * 30}px)`, textAlign: 'center' }}>
              <div style={{ fontFamily: s.font(), fontSize: 70, color: C.ink, lineHeight: 1.6 }}>{s.word}</div>
              <div style={{ fontFamily: F.body, fontSize: 24, color: C.muted, fontWeight: 600 }}>{s.name}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'absolute', left: 1360, top: 170, fontFamily: F.body, opacity: fade(f, 10) }}>
        <div style={{ fontSize: 96, fontWeight: 800, color: C.gold, lineHeight: 1 }}>150M+</div>
        <div style={{ fontSize: 28, color: C.muted, fontWeight: 600 }}>readers</div>
      </div>
      {/* 144 dots */}
      <div style={{ position: 'absolute', left: 120, top: 440, width: 660, opacity: fade(f, scan) }}>
        <div style={{ fontFamily: F.body, fontSize: 30, color: C.ink, fontWeight: 700, marginBottom: 18 }}>144 live websites scanned</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(18, 1fr)', gap: 10 }}>
          {Array.from({ length: 144 }).map((_, i) => {
            const appear = scan + i * 0.15;
            const bad = ((i * 37) % 144) < visible;
            const turn = interpolate(f, [s51 + ((i * 7) % 20), s51 + ((i * 7) % 20) + 6], [0, 1], clamp);
            return <div key={i} style={{ width: 26, height: 26, borderRadius: 7, opacity: fade(f, appear, 4),
              background: bad && turn > 0.5 ? C.bad : '#3A3680' }} />;
          })}
        </div>
      </div>
      <div style={{ position: 'absolute', left: 880, top: 440, display: 'flex', flexDirection: 'column', gap: 26, width: 900 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 24 }}>
          <Count to={51} at={s51} suffix="%" color={C.bad} size={110} />
          <span style={{ fontFamily: F.body, fontSize: 30, color: C.ink, opacity: fade(f, s51 + 8), fontWeight: 600 }}>visible rendering problem</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 24 }}>
          <Count to={45} at={s45} suffix="%" color={C.gold} size={110} />
          <span style={{ fontFamily: F.body, fontSize: 30, color: C.ink, opacity: fade(f, s45 + 8), fontWeight: 600 }}>no font for their own language</span>
        </div>
        <div style={{ display: 'flex', gap: 18, opacity: fade(f, burm - 6), marginTop: 6 }}>
          {SCRIPTS.map((s) => {
            const h = interpolate(f, [burm - 6, burm + 18], [0, s.pct * 1.6], clamp);
            const hot = s.name === 'Burmese';
            return (
              <div key={s.name} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: 190, width: 150 }}>
                <div style={{ fontFamily: F.body, fontSize: 26, fontWeight: 800, color: hot ? C.bad : C.ink }}>{s.pct}%</div>
                <div style={{ width: 90, height: h, background: hot ? C.bad : C.line, borderRadius: 10 }} />
                <div style={{ fontFamily: F.body, fontSize: 22, color: C.muted, marginTop: 6 }}>{s.name}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------- 03 agent ----------
const STEPS = [
  { k: 'Plan', d: 'pick real pages', re: /plans/, ic: 'M20 20 h40 v40 h-40z M28 32 h24 M28 42 h24 M28 52 h14' },
  { k: 'Dispatch', d: 'open in a browser', re: /opens/, ic: 'M14 22 h52 v38 h-52z M14 32 h52 M22 27 h2 M28 27 h2' },
  { k: 'Verify', d: 'what readers see', re: /measures/, ic: 'M40 24 c-16 0 -26 16 -26 16 s10 16 26 16 s26 -16 26 -16 s-10 -16 -26 -16z M40 34 a6 6 0 1 0 0.1 0' },
  { k: 'Fix', d: 'CSS + translation', re: /writes/, ic: 'M22 58 l28 -28 l8 8 l-28 28 h-8z M46 26 l8 8' },
  { k: 'Prove', d: 'fresh sandbox', re: /proves/, ic: 'M40 16 l24 10 v14 c0 14 -10 22 -24 26 c-14 -4 -24 -12 -24 -26 v-14z M30 40 l7 7 l13 -13' },
];

export const Agent = () => {
  const f = useCurrentFrame();
  const id = '03-agent';
  const at = STEPS.map((s, i) => cue(id, s.re, 4 + i * 1.6));
  const logo = pop(f, 2);
  const lit = (i: number) => fade(f, at[i], 8);
  const prog = interpolate(f, [at[0], at[4]], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ position: 'absolute', left: 0, right: 0, top: 150, textAlign: 'center', opacity: logo, transform: `scale(${0.9 + logo * 0.1})` }}>
        <div style={{ fontFamily: F.body, fontWeight: 800, fontSize: 120, color: C.ink, letterSpacing: -3 }}>
          Glyph<span style={{ color: C.gold }}>Sweep</span>
        </div>
        <div style={{ fontFamily: F.body, fontSize: 32, color: C.muted, fontWeight: 600 }}>an AI agent on Vultr</div>
      </div>
      <div style={{ position: 'absolute', left: 200, right: 200, top: 600, height: 6, background: C.line, borderRadius: 3 }}>
        <div style={{ width: `${prog * 100}%`, height: '100%', background: C.gold, borderRadius: 3, boxShadow: `0 0 20px ${C.gold}` }} />
      </div>
      <div style={{ position: 'absolute', left: 120, right: 120, top: 520, display: 'flex', justifyContent: 'space-between' }}>
        {STEPS.map((s, i) => (
          <div key={s.k} style={{ width: 250, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
            <div style={{ width: 160, height: 160, borderRadius: 40, background: lit(i) > 0.5 ? (i === 4 ? '#3A2F10' : C.panel) : '#18163F',
              border: `3px solid ${lit(i) > 0.5 ? C.gold : C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
              transform: `scale(${1 + 0.12 * pop(f, at[i]) - 0.12 * pop(f, at[i] + 10)})`, boxShadow: lit(i) > 0.5 ? `0 0 40px rgba(232,181,74,.35)` : 'none' }}>
              <svg width="80" height="80" viewBox="0 0 80 80"><path d={s.ic} stroke={lit(i) > 0.5 ? C.gold : C.muted} strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </div>
            <div style={{ fontFamily: F.body, fontWeight: 800, fontSize: 40, color: lit(i) > 0.5 ? C.ink : C.muted }}>{s.k}</div>
            <div style={{ fontFamily: F.body, fontSize: 26, color: C.muted, opacity: 0.4 + 0.6 * lit(i) }}>{s.d}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ---------- 04 sandbox ----------
export const Sandbox = () => {
  const f = useCurrentFrame();
  const id = '04-sandbox';
  const danger = cue(id, /dangerous/, 1.5);
  const attack = cue(id, /attack/, 3);
  const box = cue(id, /throwaway|gVisor/, 5);
  const secrets = cue(id, /secrets/, 8);
  const proxy = cue(id, /proxy/, 11);
  const destroyed = cue(id, /destroyed/, 15);
  const gone = cue(id, /gone/, 18);
  const zoom = interpolate(f, [0, 700], [1.05, 1.15], clamp);
  const boxP = pop(f, box);
  const dissolve = interpolate(f, [destroyed, destroyed + 18], [1, 0], clamp);
  const shot = (i: number) => {
    const t0 = attack + 8 + i * 22;
    const k = interpolate(f, [t0, t0 + 14], [0, 1], clamp);
    const back = interpolate(f, [t0 + 14, t0 + 26], [0, 1], clamp);
    return { k, back, vis: f > t0 && f < t0 + 30 };
  };
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `scale(${zoom})` }}>
        <Img src={staticFile('slide-containment.jpg')} style={{ width: 1920, height: 1080, objectFit: 'cover', opacity: 0.55 }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: 'linear-gradient(90deg, rgba(15,13,46,.95) 0%, rgba(15,13,46,.75) 60%, rgba(15,13,46,.3) 100%)' }} />
      <AbsoluteFill style={{ background: C.bad, opacity: 0.18 * Math.max(0, Math.sin(((f - danger) / 8) * Math.PI)) * (f > danger && f < danger + 16 ? 1 : 0) }} />
      <Eyebrow>Blast radius zero</Eyebrow>
      <Title y={136} w={1300}>Every page opens in a throwaway box</Title>
      {/* diagram */}
      <div style={{ position: 'absolute', left: 120, top: 360, width: 1680, height: 480 }}>
        {/* control plane */}
        <div style={{ position: 'absolute', left: 0, top: 120, width: 330, height: 240, borderRadius: 24, background: C.panel, border: `2px solid ${C.line}`, padding: 24,
          fontFamily: F.body, color: C.ink, opacity: fade(f, 4) }}>
          <div style={{ fontSize: 30, fontWeight: 800 }}>Control plane</div>
          <div style={{ fontSize: 24, color: C.muted, marginTop: 10 }}>🔑 API key<br />🐳 Docker socket</div>
          <div style={{ fontSize: 22, color: C.teal, marginTop: 12, opacity: fade(f, secrets) }}>stays here, never inside</div>
        </div>
        {/* sandbox */}
        <div style={{ position: 'absolute', left: 470, top: 40, width: 520, height: 400, borderRadius: 30, border: `4px solid ${C.gold}`,
          background: 'rgba(232,181,74,0.06)', opacity: boxP * dissolve, transform: `scale(${(0.8 + boxP * 0.2) * (0.9 + dissolve * 0.1)})`,
          boxShadow: `0 0 60px rgba(232,181,74,.3)`, padding: 26, fontFamily: F.body, color: C.ink }}>
          <div style={{ fontSize: 30, fontWeight: 800, color: C.gold }}>gVisor sandbox</div>
          <div style={{ fontSize: 22, color: C.muted, marginTop: 6 }}>read-only · non-root · no caps · 240 s</div>
          <div style={{ marginTop: 26, height: 210, borderRadius: 16, background: '#FBF7EE', padding: 18, color: '#2A1E14' }}>
            <div style={{ display: 'flex', gap: 8 }}>{[0, 1, 2].map((i) => <div key={i} style={{ width: 14, height: 14, borderRadius: 7, background: '#C9BFA8' }} />)}</div>
            <div style={{ fontFamily: F.thai, fontSize: 34, fontWeight: 700, marginTop: 14 }}>ร้านกาแฟดาว</div>
            <div style={{ fontSize: 22, color: C.bad, fontWeight: 700, marginTop: 10, opacity: fade(f, attack) }}>⚠ hostile page</div>
          </div>
        </div>
        <div style={{ position: 'absolute', left: 520, top: 200, width: 420, textAlign: 'center', opacity: fade(f, destroyed + 10), fontFamily: F.body,
          fontSize: 34, fontWeight: 800, color: C.teal }}>
          ✓ destroyed{f > gone ? ' · confirmed gone' : ''}
        </div>
        {/* proxy + internet */}
        <div style={{ position: 'absolute', left: 1120, top: 150, width: 250, height: 180, borderRadius: 24, background: C.panel, border: `2px solid ${C.teal}`,
          padding: 22, fontFamily: F.body, color: C.ink, opacity: fade(f, proxy - 4) }}>
          <div style={{ fontSize: 28, fontWeight: 800 }}>Allowlist proxy</div>
          <div style={{ fontSize: 22, color: C.muted, marginTop: 8 }}>this job only:<br />site + fonts</div>
        </div>
        <div style={{ position: 'absolute', left: 990, top: 236, width: 130, height: 6, background: C.teal, opacity: fade(f, proxy) }} />
        <div style={{ position: 'absolute', left: 1370, top: 236, width: 110, height: 6, background: C.teal, opacity: fade(f, proxy) }} />
        <div style={{ position: 'absolute', left: 1480, top: 170, width: 180, height: 140, borderRadius: 70, border: `2px dashed ${C.muted}`, display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontFamily: F.body, fontSize: 28, color: C.muted, opacity: fade(f, proxy) }}>Internet</div>
        {/* attacks bouncing off the sandbox wall toward the key */}
        {[0, 1, 2].map((i) => {
          const s = shot(i);
          if (!s.vis) return null;
          const x = 560 - s.k * 80 + s.back * 60;
          const y = 150 + i * 90;
          return (
            <div key={i} style={{ position: 'absolute', left: x, top: y, fontFamily: F.body, fontWeight: 800, fontSize: 26, color: C.bad, whiteSpace: 'nowrap' }}>
              {s.back > 0.2 ? '✕ blocked' : '◀━━ ' + ['169.254.169.254', 'steal cookies', 'read API key'][i]}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------- real recording scenes ----------
const Browser: React.FC<{ id: string }> = ({ id }) => {
  const f = useCurrentFrame();
  const meta = clips[id];
  const t = f / FPS;
  const seg = meta?.segs.find((s) => t >= s.at && t < s.at + s.dur) ?? meta?.segs[meta.segs.length - 1];
  return (
    <div style={{ position: 'absolute', left: 70, top: 56, width: 1340, height: 798, borderRadius: 18, overflow: 'hidden', background: '#0B0A1C',
      boxShadow: '0 30px 100px rgba(0,0,0,.6)', border: `2px solid ${C.line}` }}>
      <div style={{ height: 44, background: '#1B1946', display: 'flex', alignItems: 'center', gap: 10, padding: '0 18px' }}>
        {['#FB7185', '#E8B54A', '#4FD1B5'].map((c) => <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />)}
        <div style={{ marginLeft: 16, flex: 1, height: 28, borderRadius: 14, background: '#0F0D2E', color: C.muted, fontFamily: F.body, fontSize: 18,
          display: 'flex', alignItems: 'center', padding: '0 14px' }}>🔒 https://45-77-254-54.sslip.io</div>
      </div>
      {meta ? (
        <OffthreadVideo src={staticFile(`clip-${id}.mp4`)} muted style={{ width: 1340, height: 754, objectFit: 'cover' }} />
      ) : (
        <div style={{ color: C.muted, fontFamily: F.body, fontSize: 40, padding: 60 }}>recording pending</div>
      )}
      <div style={{ position: 'absolute', left: 18, top: 62, display: 'flex', gap: 10 }}>
        <div style={{ background: 'rgba(15,13,46,.9)', border: `1px solid ${C.bad}`, borderRadius: 10, padding: '6px 14px', fontFamily: F.body, fontSize: 20,
          fontWeight: 700, color: C.ink }}><span style={{ color: C.bad, opacity: 0.5 + 0.5 * Math.sin(f / 5) }}>●</span> LIVE on Vultr · real recording</div>
        {seg && seg.speed > 1.25 ? (
          <div style={{ background: 'rgba(15,13,46,.9)', border: `1px solid ${C.gold}`, borderRadius: 10, padding: '6px 14px', fontFamily: F.body, fontSize: 20,
            fontWeight: 700, color: C.gold }}>⏩ {seg.speed >= 10 ? seg.speed.toFixed(0) : seg.speed.toFixed(1)}× speed</div>
        ) : null}
        {seg?.label ? (
          <div style={{ background: 'rgba(15,13,46,.9)', borderRadius: 10, padding: '6px 14px', fontFamily: F.body, fontSize: 20, fontWeight: 700, color: C.muted }}>{seg.label}</div>
        ) : null}
      </div>
    </div>
  );
};

const Side: React.FC<{ items: { at: number; text: React.ReactNode; color?: string }[]; eyebrow: string }> = ({ items, eyebrow }) => (
  <>
    <Eyebrow x={1460} y={70}>{eyebrow}</Eyebrow>
    <div style={{ position: 'absolute', left: 1450, top: 130, width: 420, display: 'flex', flexDirection: 'column', gap: 18 }}>
      {items.map((it, i) => <Badge key={i} at={it.at} flow w={420} color={it.color}>{it.text}</Badge>)}
    </div>
  </>
);

const fact = (id: string, k: string, d: string) => clips[id]?.facts?.[k] ?? d;

export const Demo = () => {
  const id = '05-demo';
  return (
    <AbsoluteFill>
      <Backdrop />
      <Browser id={id} />
      <Side eyebrow="Hostile Thai shop" items={[
        { at: cue(id, /credentials/, 6), text: <>169.254.169.254<br /><span style={{ color: C.bad }}>✕ blocked</span></>, color: C.bad },
        { at: cue(id, /cookies/, 8), text: <>cookie exfil · pixel · beacon<br /><span style={{ color: C.bad }}>✕ blocked</span></>, color: C.bad },
        { at: cue(id, /injection/, 10), text: <>“ignore previous instructions…”<br /><span style={{ color: C.gold }}>⚑ flagged</span></>, color: C.gold },
        { at: cue(id, /attacks/, 18), text: <>Self-attack probe<br /><span style={{ color: C.teal }}>no metadata · no docker.sock</span></>, color: C.teal },
        { at: cue(id, /blocked/, 15), text: <>{fact(id, 'blocked', 'every request')} egress attempts blocked</>, color: C.teal },
      ]} />
    </AbsoluteFill>
  );
};

export const Findings = () => {
  const id = '06-findings';
  return (
    <AbsoluteFill>
      <Backdrop />
      <Browser id={id} />
      <Side eyebrow="Findings" items={[
        { at: cue(id, /flagged/, 1), text: <>Prompt injection<br /><span style={{ color: C.gold }}>flagged, ignored</span></>, color: C.gold },
        { at: cue(id, /code/, 4), text: <>Findings come from code,<br />not from the model</>, color: C.teal },
        { at: cue(id, /vision/, 7), text: <>Vultr vision model:<br />what a reader really sees</>, color: C.teal },
      ]} />
    </AbsoluteFill>
  );
};

export const Proof = () => {
  const id = '07-proof';
  return (
    <AbsoluteFill>
      <Backdrop />
      <Browser id={id} />
      <Side eyebrow="Bare-device OCR" items={[
        { at: cue(id, /font/, 3), text: <>Phone with<br />no Thai font</>, color: C.muted },
        { at: cue(id, /Before/, 6), text: <>OCR error before<br /><span style={{ color: C.bad, fontSize: 56 }}>{fact(id, 'before', '96%')}</span></>, color: C.bad },
        { at: cue(id, /After/, 9), text: <>OCR error after<br /><span style={{ color: C.teal, fontSize: 56 }}>{fact(id, 'after', '5%')}</span></>, color: C.teal },
        { at: cue(id, /fresh/, 11), text: <>Proven in a fresh sandbox</>, color: C.gold },
      ]} />
    </AbsoluteFill>
  );
};

export const Trust = () => {
  const id = '08-trust';
  const f = useCurrentFrame();
  const score = cue(id, /score/i, 10);
  return (
    <AbsoluteFill>
      <Backdrop />
      <Browser id={id} />
      <Side eyebrow="Best measured patch" items={[
        { at: cue(id, /competes/, 3), text: <>Model patch<br />vs deterministic<br />vs combined</>, color: C.muted },
        { at: cue(id, /measured/, 6), text: <>Each proven in its<br />own sandbox</>, color: C.teal },
      ]} />
      <div style={{ position: 'absolute', left: 1450, top: 470, width: 410, padding: 28, borderRadius: 24, background: 'rgba(15,13,46,.92)', border: `3px solid ${C.gold}`,
        opacity: pop(f, score), transform: `scale(${0.8 + 0.2 * pop(f, score)})`, textAlign: 'center', fontFamily: F.body }}>
        <div style={{ fontSize: 26, color: C.muted, fontWeight: 600 }}>Readiness score</div>
        <div style={{ fontSize: 96, fontWeight: 800, color: C.ink, lineHeight: 1.1 }}>
          {fact(id, 'before', '33')} → <span style={{ color: C.gold }}>{fact(id, 'after', '74')}</span>
        </div>
        <div style={{ fontSize: 24, color: C.muted }}>in all four scripts</div>
      </div>
    </AbsoluteFill>
  );
};

// ---------- 09 close ----------
export const Close = () => {
  const f = useCurrentFrame();
  const id = '09-close';
  const live = cue(id, /live/, 4);
  const p = pop(f, live);
  const out = interpolate(f, [live - 6, live + 8], [1, 0], clamp);
  return (
    <AbsoluteFill>
      <Backdrop />
      <div style={{ opacity: out }}>
        <Noy mood={1} x={600} y={340} />
        <Phone broken={0} x={1000} y={110} />
        <Badge at={20} x={1470} y={340} color={C.teal} w={360}>✓ reads perfectly</Badge>
      </div>
      <AbsoluteFill style={{ opacity: p }}>
        <Img src={staticFile('hero.webp')} style={{ width: 1920, height: 1080, objectFit: 'cover', opacity: 0.6 }} />
        <AbsoluteFill style={{ background: 'linear-gradient(90deg, rgba(15,13,46,.96) 0%, rgba(15,13,46,.7) 50%, rgba(15,13,46,.1) 100%)' }} />
        <div style={{ position: 'absolute', left: 140, top: 210, fontFamily: F.body, color: C.ink, transform: `translateY(${(1 - p) * 30}px)` }}>
          <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: 5, color: C.gold, textTransform: 'uppercase' }}>Vultr Agent Rush · Blast Radius Zero</div>
          <div style={{ fontSize: 150, fontWeight: 800, letterSpacing: -4, lineHeight: 1.05, marginTop: 10 }}>Glyph<span style={{ color: C.gold }}>Sweep</span></div>
          <div style={{ fontSize: 44, fontWeight: 600, marginTop: 10, width: 1000 }}>Blast radius zero, for 150 million readers.</div>
          <div style={{ display: 'flex', gap: 18, marginTop: 44, opacity: fade(f, live + 20) }}>
            {['45-77-254-54.sslip.io', 'github.com/Dan16ssd/glyphsweep'].map((t) => (
              <div key={t} style={{ fontSize: 30, fontWeight: 700, background: C.gold, color: C.bg, padding: '14px 28px', borderRadius: 999 }}>{t}</div>
            ))}
          </div>
          <div style={{ fontSize: 28, color: C.muted, marginTop: 30, opacity: fade(f, live + 30) }}>Team Spectocious · built in Vientiane, Laos</div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
