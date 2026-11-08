// Red-team helper: every attack records what it tried and what the browser saw.
// The verdict is NOT taken from here: the control plane decides from the proxy log
// and the sandbox's own evidence. This is only the page's side of the story.
window.__rt = { attempts: [], done: false };
window.rt = (what, p) => {
  const rec = { what, outcome: 'pending' };
  window.__rt.attempts.push(rec);
  return Promise.race([
    Promise.resolve().then(p).then(
      (v) => (rec.outcome = 'REACHED: ' + String(v).slice(0, 100)),
      (e) => (rec.outcome = 'failed: ' + String((e && e.message) || e).slice(0, 100))),
    new Promise((r) => setTimeout(() => { if (rec.outcome === 'pending') rec.outcome = 'failed: no response in 6s'; r(); }, 6000)),
  ]);
};
window.rtDone = (ps) => Promise.allSettled(ps).then(() => (window.__rt.done = true));
window.viaProxy = (r) => {
  if (r.status === 403 || r.status === 502) throw new Error(r.status + ' from the egress proxy');
  return 'HTTP ' + r.status;
};
