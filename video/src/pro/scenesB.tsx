import React from 'react';
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { F } from '../theme';
import rtJson from '../../public/redteam.json';
import { Fig, Grid, H, Header, Live, P, PF, Tag, clamp, cue, ease, fade } from './kit';

const RT = rtJson as { id: string; contained: number; total: number; runtime: string; seconds: number; sandboxes: number; rows: { tier: string; attack: string; contained: boolean }[] };

// ---------------------------------------------------------------- §6 containment, 3D exploded
const LAYERS = [
  { t: 'Vultr Cloud Compute VM', s: 'Singapore · runs everything below', c: P.blue },
  { t: 'Docker + gVisor (runsc)', s: 'user-space kernel between page and host', c: P.violet },
  { t: 'Sandbox container', s: 'read-only · uid 1000 · cap_drop ALL · 1.5 GB · 240 s', c: P.amber },
  { t: 'Headless Chromium', s: 'detectors · screenshots · OCR', c: P.pass },
  { t: 'The web page', s: 'untrusted, maybe hostile', c: P.fail },
];
const SPECS: [string, string, RegExp, number][] = [
  ['runtime', 'runsc (gVisor)', /gVisor/, 2.5],
  ['rootfs', 'read-only', /read-only/, 4.5],
  ['user', 'uid 1000, cap_drop ALL', /non-root/, 5.2],
  ['limits', '1.5 GB · 1.5 vCPU · 512 PIDs · 240 s', /limits/, 7.5],
  ['egress', 'per-job allowlist proxy only', /proxy/, 11],
  ['secrets', '0 (key stays in control plane)', /key/, 13],
  ['lifecycle', 'destroyed + verified gone', /destroyed/, 16.5],
];
export const Arch = () => {
  const f = useCurrentFrame();
  const id = 'p06-arch';
  const gap = interpolate(f, [10, 90], [26, 92], clamp);
  const rotZ = interpolate(f, [0, 600], [-48, -28], clamp);
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={6} title="Containment" />
      <H w={900}>Every page is treated as hostile</H>
      {/* 3D stack */}
      <div style={{ position: 'absolute', left: 960, top: 120, width: 900, height: 860, perspective: 2200 }}>
        <div style={{ position: 'absolute', left: 170, top: 360, width: 340, height: 340, transformStyle: 'preserve-3d',
          transform: `rotateX(60deg) rotateZ(${rotZ}deg)` }}>
          {LAYERS.map((l, i) => {
            const e = ease(f, 4 + i * 6);
            return (
              <div key={l.t} style={{ position: 'absolute', inset: 0, transform: `translateZ(${i * gap * e}px)`, border: `2px solid ${l.c}`,
                background: `linear-gradient(135deg, ${l.c}30, ${l.c}0c)`, boxShadow: `0 0 40px ${l.c}22`, opacity: e,
                backgroundImage: `linear-gradient(${l.c}22 1px, transparent 1px), linear-gradient(90deg, ${l.c}22 1px, transparent 1px)`, backgroundSize: '42px 42px' }} />
            );
          })}
        </div>
        {/* labels (2D) */}
        {LAYERS.map((l, i) => (
          <div key={l.t} style={{ position: 'absolute', left: 610, top: 610 - i * gap * 0.92 - 40, opacity: fade(f, 20 + i * 6), fontFamily: PF.sans, width: 330 }}>
            <div style={{ fontSize: 22, fontWeight: 600, color: l.c, whiteSpace: 'nowrap' }}>{l.t}</div>
            <div style={{ fontSize: 14, color: P.mute, fontFamily: PF.mono }}>{l.s}</div>
          </div>))}
      </div>
      {/* spec sheet */}
      <div style={{ position: 'absolute', left: 96, top: 270, width: 820, border: `1px solid ${P.line2}`, background: P.panel }}>
        <div style={{ fontFamily: PF.mono, fontSize: 16, color: P.dim, padding: '12px 20px', borderBottom: `1px solid ${P.line}` }}>SANDBOX SPEC · per stage, per job</div>
        {SPECS.map(([k, v, re, fb]) => {
          const at = cue(id, re, fb);
          const on = fade(f, at, 8);
          return (
            <div key={k} style={{ display: 'grid', gridTemplateColumns: '160px 1fr 40px', padding: '13px 20px', borderBottom: `1px solid ${P.line}`, fontFamily: PF.mono,
              fontSize: 23, background: on > 0.5 && f < at + 45 ? '#1A2230' : 'transparent' }}>
              <span style={{ color: P.mute }}>{k}</span><span style={{ color: P.ink, opacity: 0.35 + 0.65 * on }}>{v}</span>
              <span style={{ color: P.pass, opacity: on }}>✓</span>
            </div>);
        })}
      </div>
      <Fig n="6" x={96} y={960} at={20}>Exploded view of one sandbox. The control plane (FastAPI, Docker socket, API key) sits outside it.</Fig>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §7 hostile demo (real recording)
const LOG: [string, string, string, RegExp, number][] = [
  ['DENY', '169.254.169.254:80', 'cloud metadata', /credentials/, 3],
  ['DENY', 'exfil host · cookies', 'not on allowlist', /cookies/, 5],
  ['DENY', 'tracking pixel · sendBeacon', 'not on allowlist', /cookies/, 5.8],
  ['FLAG', '"ignore previous instructions…"', 'prompt injection', /inject/, 7],
  ['KEEP', 'all 31 findings reported', 'model cannot delete', /reported/, 11],
];
export const Hostile = () => {
  const f = useCurrentFrame();
  const id = 'p07-hostile';
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={7} title="Adversarial test" />
      <H w={1000}>The demo shop fights back</H>
      <div style={{ position: 'absolute', left: 96, top: 220, width: 1060, height: 640, border: `1px solid ${P.line2}`, overflow: 'hidden', background: '#000' }}>
        <OffthreadVideo src={staticFile('clip-05-demo.mp4')} startFrom={Math.round(8.6 * 30)} muted style={{ width: 1060, height: 640, objectFit: 'cover', objectPosition: 'top' }} />
      </div>
      <Live x={110} y={876} at={0}>REAL RECORDING · LIVE ON VULTR · CONTAINMENT TAB</Live>
      <div style={{ position: 'absolute', left: 1200, top: 220, width: 624, border: `1px solid ${P.line2}`, background: P.panel }}>
        <div style={{ fontFamily: PF.mono, fontSize: 16, color: P.dim, padding: '12px 18px', borderBottom: `1px solid ${P.line}` }}>EGRESS PROXY + AGENT LOG</div>
        {LOG.map(([a, t, r, re, fb]) => {
          const at = cue(id, re, fb);
          const c = a === 'DENY' ? P.fail : a === 'FLAG' ? P.amber : P.pass;
          return (
            <div key={t} style={{ padding: '16px 18px', borderBottom: `1px solid ${P.line}`, opacity: fade(f, at, 8), fontFamily: PF.mono }}>
              <span style={{ color: c, fontWeight: 600, marginRight: 14 }}>{a}</span><span style={{ color: P.ink, fontSize: 21 }}>{t}</span>
              <div style={{ color: P.mute, fontSize: 17, marginTop: 4, marginLeft: 66 }}>{r}</div>
            </div>);
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §8 red team
const SBX = [
  { n: '#1', t: 'hostile pages', s: 13.9, end: 'exit 0', c: P.pass },
  { n: '#2', t: 'crash page', s: 4.1, end: 'OOM-killed', c: P.amber },
  { n: '#3', t: 'code execution', s: 3.0, end: 'exit 0', c: P.pass },
  { n: '#4', t: 'memory bomb', s: 2.1, end: 'OOM-killed', c: P.amber },
  { n: '#5', t: 'never exit', s: 20.6, end: 'killed at limit', c: P.amber },
];
const TIER_C: Record<string, string> = { browser: P.blue, agent: P.violet, 'code-exec': P.fail, lifecycle: P.pass };
export const RedTeam = () => {
  const f = useCurrentFrame();
  const id = 'p08-redteam';
  const go = cue(id, /five/, 3);
  const verdict = cue(id, /Forty-three/, 10);
  const n = Math.round(interpolate(f, [go + 10, verdict + 20], [0, RT.contained], clamp));
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={8} title="Red team" />
      <H w={1100}>We attack our own sandbox</H>
      {/* matrix */}
      <div style={{ position: 'absolute', left: 96, top: 240, width: 860 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(9, 1fr)', gap: 10 }}>
          {RT.rows.map((r, i) => {
            const on = i < n;
            const c = TIER_C[r.tier] ?? P.pass;
            return (
              <div key={i} style={{ height: 66, border: `1.5px solid ${on ? c : P.line2}`, background: on ? `${c}26` : '#121821', position: 'relative' }}>
                <span style={{ position: 'absolute', left: 6, top: 4, fontFamily: PF.mono, fontSize: 13, color: on ? c : P.dim }}>{String(i + 1).padStart(2, '0')}</span>
                <span style={{ position: 'absolute', right: 8, bottom: 4, fontFamily: PF.mono, fontSize: 22, color: P.pass, opacity: on ? 1 : 0 }}>✓</span>
              </div>);
          })}
        </div>
        <div style={{ display: 'flex', gap: 22, marginTop: 18, fontFamily: PF.mono, fontSize: 17, color: P.mute }}>
          {Object.entries(TIER_C).map(([k, c]) => <span key={k}><span style={{ color: c }}>■</span> {k}</span>)}
        </div>
      </div>
      <div style={{ position: 'absolute', left: 96, top: 720, fontFamily: PF.mono, opacity: fade(f, verdict - 6) }}>
        <span style={{ fontSize: 120, color: P.pass, letterSpacing: -4 }}>{n}/{RT.total}</span>
        <span style={{ fontSize: 30, color: P.ink, marginLeft: 22 }}>contained</span>
      </div>
      {/* sandbox lifecycles */}
      <div style={{ position: 'absolute', left: 1030, top: 240, width: 794, border: `1px solid ${P.line2}`, background: P.panel, opacity: fade(f, go - 4) }}>
        <div style={{ fontFamily: PF.mono, fontSize: 16, color: P.dim, padding: '12px 18px', borderBottom: `1px solid ${P.line}` }}>SANDBOX LIFETIMES (s) · run {RT.id} · {RT.runtime}</div>
        {SBX.map((s, i) => {
          const w = (s.s / 22) * 330 * fade(f, go + i * 6, 20);
          return (
            <div key={s.n} style={{ display: 'grid', gridTemplateColumns: '230px 1fr', alignItems: 'center', padding: '14px 18px', borderBottom: `1px solid ${P.line}` }}>
              <div style={{ fontFamily: PF.sans, fontSize: 21, color: P.ink }}><span style={{ fontFamily: PF.mono, color: P.dim }}>{s.n}</span> {s.t}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: w, height: 18, background: s.c }} />
                <span style={{ fontFamily: PF.mono, fontSize: 16, color: P.mute, whiteSpace: 'nowrap' }}>{s.s}s · {s.end}</span>
              </div>
            </div>);
        })}
        <div style={{ fontFamily: PF.mono, fontSize: 17, color: P.mute, padding: '14px 18px', lineHeight: 1.5 }}>
          All 5 destroyed and verified gone. Verdicts from the egress proxy log and Docker state.<br />Hosts reached outside the allowlist: <span style={{ color: P.pass }}>none</span>
        </div>
      </div>
      <Live x={1040} y={720} at={verdict}>RE-RUN IT: 45-77-254-54.sslip.io/#redteam</Live>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §9 approval
export const Approve = () => {
  const f = useCurrentFrame();
  const id = 'p09-approve';
  const L: [string, string, RegExp, number][] = [['The model proposes.', P.amber, /proposes/, 0.3], ['Measurements decide.', P.blue, /Measurements/, 1.5], ['A human releases.', P.pass, /human/, 3]];
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={9} title="Human in the loop" />
      <div style={{ position: 'absolute', left: 96, top: 250 }}>
        {L.map(([t, c, re, fb]) => {
          const e = ease(f, cue(id, re, fb));
          return <div key={t} style={{ fontFamily: PF.sans, fontWeight: 600, fontSize: 76, color: P.ink, letterSpacing: -2, opacity: e, transform: `translateX(${(1 - e) * -24}px)`,
            borderLeft: `6px solid ${c}`, paddingLeft: 26, marginBottom: 26 }}>{t}</div>;
        })}
        <div style={{ fontFamily: PF.mono, fontSize: 20, color: P.mute, marginTop: 30, width: 980, opacity: fade(f, cue(id, /locked/, 5)) }}>
          GET /patch.css → <span style={{ color: P.fail }}>403</span> until a person approves · decision logged in the timeline</div>
      </div>
      <div style={{ position: 'absolute', left: 1130, top: 200, width: 700, height: 700, border: `1px solid ${P.line2}`, overflow: 'hidden', background: '#000' }}>
        <OffthreadVideo src={staticFile('clip-085-approve.mp4')} startFrom={30} muted style={{ width: 1400, height: 787, marginLeft: -60, marginTop: -40 }} />
      </div>
      <Live x={1140} y={914} at={0}>REAL RECORDING · APPROVE & RELEASE</Live>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §10 business
const YAML = [
  ['- uses: ', 'Dan16ssd/glyphsweep@main'],
  ['  with:', ''],
  ['    url: ', 'https://staging.shop.la/checkout'],
  ['    script: ', 'lao'],
  ['    min-score: ', '"70"'],
];
export const Business = () => {
  const f = useCurrentFrame();
  const id = 'p10-business';
  const sold = cue(id, /Sold/, 4.5);
  const next = cue(id, /Unicode/, 12);
  return (
    <AbsoluteFill>
      <Grid />
      <Header n={10} title="Product" />
      <H w={1700}>A release gate for the checkout people actually see</H>
      <div style={{ position: 'absolute', left: 96, top: 250, width: 820, border: `1px solid ${P.line2}`, background: '#0C1016', padding: '20px 26px', fontFamily: PF.mono, fontSize: 25 }}>
        <div style={{ fontSize: 15, color: P.dim, marginBottom: 10 }}>.github/workflows/release.yml</div>
        {YAML.map(([a, b], i) => <div key={i} style={{ opacity: fade(f, 6 + i * 5, 6), color: P.mute, whiteSpace: 'pre' }}>{a}<span style={{ color: P.amber }}>{b}</span></div>)}
      </div>
      <div style={{ position: 'absolute', left: 96, top: 540, width: 820, border: `1px solid ${P.fail}`, background: P.panel, padding: '18px 26px', opacity: fade(f, 34) }}>
        <div style={{ fontFamily: PF.sans, fontSize: 27, fontWeight: 600, color: P.ink }}><span style={{ color: P.fail }}>✗</span> GlyphSweep thai readiness: 33/100 (gate: 70)</div>
        <div style={{ fontFamily: PF.mono, fontSize: 19, color: P.mute, marginTop: 10, lineHeight: 1.6 }}>
          with proven patch: 74 · bare-phone OCR error 96% → 5%<br />patch locked until a human approves → link
        </div>
        <div style={{ fontFamily: PF.mono, fontSize: 15, color: P.dim, marginTop: 8 }}>real run: github.com/Dan16ssd/glyphsweep/actions</div>
      </div>
      <div style={{ position: 'absolute', left: 1000, top: 250, width: 824 }}>
        <div style={{ fontFamily: PF.mono, fontSize: 16, color: P.dim, marginBottom: 12, opacity: fade(f, sold) }}>WHO PAYS · per site, per month</div>
        {[['Banks & telcos', 'apps used on budget Android phones'], ['Online shops', 'checkout, prices, product names'], ['Localization agencies', 'machine proof for every delivery'], ['Government portals', 'accessibility + lang compliance']].map(([t, s], i) => (
          <div key={t} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '16px 0', borderBottom: `1px solid ${P.line}`, opacity: fade(f, sold + 6 + i * 6) }}>
            <span style={{ fontFamily: PF.sans, fontSize: 29, fontWeight: 600, color: P.ink }}>{t}</span>
            <span style={{ fontFamily: PF.sans, fontSize: 20, color: P.mute }}>{s}</span>
          </div>))}
        <div style={{ marginTop: 40, opacity: fade(f, next) }}>
          <div style={{ fontFamily: PF.mono, fontSize: 16, color: P.dim, marginBottom: 14 }}>NEXT SCRIPTS · a Unicode range + two fonts each</div>
          <div style={{ display: 'flex', gap: 16 }}>
            {[['हिन्दी', F.deva, 'Hindi'], ['العربية', F.arabic, 'Arabic'], ['བོད་ཡིག', F.tibetan, 'Tibetan'], ['සිංහල', F.sinhala, 'Sinhala']].map(([w, ff, n], i) => (
              <div key={n} style={{ border: `1px solid ${P.line2}`, padding: '6px 18px', textAlign: 'center', opacity: fade(f, next + 4 + i * 4) }}>
                <div style={{ fontFamily: ff, fontSize: 36, color: P.ink, lineHeight: 1.6 }}>{w}</div>
                <div style={{ fontFamily: PF.mono, fontSize: 15, color: P.mute }}>{n}</div>
              </div>))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- §11 close
export const Close = () => {
  const f = useCurrentFrame();
  const e = ease(f, 4);
  return (
    <AbsoluteFill>
      <Grid />
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', flexDirection: 'column' }}>
        <div style={{ fontFamily: PF.sans, fontWeight: 600, fontSize: 130, color: P.ink, letterSpacing: -4, opacity: e, transform: `scale(${0.96 + 0.04 * e})` }}>
          Glyph<span style={{ color: P.amber }}>Sweep</span></div>
        <div style={{ fontFamily: PF.sans, fontSize: 38, color: P.mute, marginTop: 6, opacity: fade(f, 16) }}>Every script, readable on every phone.</div>
        <div style={{ display: 'flex', gap: 28, marginTop: 30, fontFamily: F.lao, fontSize: 40, color: P.ink, opacity: fade(f, 24) }}>
          <span>ພາສາລາວ</span><span style={{ fontFamily: F.thai }}>ภาษาไทย</span><span style={{ fontFamily: F.khmer }}>ភាសាខ្មែរ</span><span style={{ fontFamily: F.myanmar }}>မြန်မာ</span>
        </div>
        <div style={{ marginTop: 56, fontFamily: PF.mono, fontSize: 25, color: P.ink, textAlign: 'center', lineHeight: 1.7, opacity: fade(f, 34) }}>
          <span style={{ color: P.amber }}>live</span> 45-77-254-54.sslip.io<br />
          <span style={{ color: P.amber }}>code</span> github.com/Dan16ssd/glyphsweep
        </div>
        <div style={{ marginTop: 40, display: 'flex', gap: 14, opacity: fade(f, 44) }}>
          <Tag color={P.blue}>Vultr Cloud Compute</Tag><Tag color={P.amber}>Vultr Serverless Inference</Tag><Tag color={P.violet}>gVisor</Tag><Tag color={P.pass}>Built in Vientiane</Tag>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
