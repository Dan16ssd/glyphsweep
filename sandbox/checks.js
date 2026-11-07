// GlyphSweep in-page detectors. Runs inside the sandboxed browser.
// Pure DOM/CSS measurement: deterministic, no model involved, cannot be talked out of a finding.
async ({ script, sentinels }) => {
  const RANGES = {
    lao: [0x0e80, 0x0eff],
    thai: [0x0e00, 0x0e7f],
    khmer: [0x1780, 0x17ff],
    myanmar: [0x1000, 0x109f],
  };
  const LANG = { lao: "lo", thai: "th", khmer: "km", myanmar: "my" };
  const SAMPLE = {
    lao: "ກ່າເຟ້ ຂໍ້ ສຸດ ໃຫຍ່ ຫຼວງ",
    thai: "กาแฟ น้ำ ปั่น ที่สุด",
    khmer: "កាហ្វេ ល្អ បំផុត",
    myanmar: "ကော်ဖီ အကောင်းဆုံး",
  };
  const [lo, hi] = RANGES[script];
  const isTarget = (c) => { const n = c.codePointAt(0); return n >= lo && n <= hi; };
  const countTarget = (s) => { let k = 0; for (const c of s) if (isTarget(c)) k++; return k; };
  const countLatin = (s) => (s.match(/[A-Za-z]/g) || []).length;

  await document.fonts.ready;

  const findings = [];
  let fid = 0;
  const add = (check, severity, el, detail) => {
    const r = el ? el.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0 };
    findings.push({
      id: `f${++fid}`,
      check,
      severity,
      selector: el ? cssPath(el) : "html",
      text: el ? (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 120) : "",
      bbox: { x: Math.round(r.x + scrollX), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height) },
      detail,
    });
  };

  function cssPath(el) {
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 5) {
      let p = el.tagName.toLowerCase();
      if (el.id) { parts.unshift(`${p}#${CSS.escape(el.id)}`); break; }
      const cls = [...el.classList].slice(0, 2).map((c) => "." + CSS.escape(c)).join("");
      p += cls;
      const sib = el.parentElement ? [...el.parentElement.children].filter((x) => x.tagName === el.tagName) : [];
      if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(el) + 1})`;
      parts.unshift(p);
      el = el.parentElement;
    }
    return parts.join(" > ");
  }

  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  };

  // Elements that directly own text (not just inherit it from children).
  const owners = [];
  const skip = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "TEMPLATE", "SVG"]);
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  let totalTarget = 0, totalLatin = 0;
  while (walker.nextNode()) {
    const t = walker.currentNode;
    const el = t.parentElement;
    if (!el || skip.has(el.tagName) || !t.textContent.trim()) continue;
    if (!visible(el)) continue;
    totalTarget += countTarget(t.textContent);
    totalLatin += countLatin(t.textContent);
    if (!seen.has(el)) { seen.add(el); owners.push(el); }
  }
  const inkCtx = document.createElement("canvas").getContext("2d");
  // How far glyph ink spills outside the element's clipping box (px, top/bottom), assuming the
  // first line starts at the top padding edge. Uses real ink bounds, which layout metrics ignore.
  const inkSpill = (el, cs) => {
    inkCtx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const m = inkCtx.measureText(ownText(el).trim());
    const fs = parseFloat(cs.fontSize);
    const lh = cs.lineHeight === "normal" ? fs * 1.2 : parseFloat(cs.lineHeight);
    const fa = m.fontBoundingBoxAscent, fd = m.fontBoundingBoxDescent;
    const baseline = parseFloat(cs.paddingTop) + (lh - (fa + fd)) / 2 + fa;
    const lines = Math.max(1, Math.round((el.scrollHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)) / lh));
    const lastBaseline = baseline + (lines - 1) * lh;
    return {
      top: Math.max(0, m.actualBoundingBoxAscent - baseline),
      bottom: Math.max(0, lastBaseline + m.actualBoundingBoxDescent - el.clientHeight),
    };
  };
  const ownText = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join(" ");
  const targetOwners = owners.filter((el) => countTarget(ownText(el)) > 0);
  const share = totalTarget / Math.max(1, totalTarget + totalLatin);

  // 1. Document language attribute
  const htmlLang = (document.documentElement.getAttribute("lang") || "").toLowerCase();
  if (share > 0.3 && !htmlLang.startsWith(LANG[script])) {
    add("html_lang", "high", null, {
      found: htmlLang || "(missing)",
      expected: LANG[script],
      why: "Screen readers, hyphenation and browser line-breaking pick rules from lang. Wrong lang = wrong pronunciation and wrong breaks.",
    });
  }

  // 2. Untranslated UI strings on a target-language page
  if (share > 0.3) {
    let n = 0;
    for (const el of owners) {
      const s = ownText(el).trim();
      if (countTarget(s) === 0 && (s.match(/[A-Za-z]{2,}/g) || []).length >= 2 && n < 15) {
        if (el.closest("[translate=no], .notranslate")) continue;
        add("untranslated", "medium", el, { string: s.slice(0, 120) });
        n++;
      }
    }
  }

  // Per-element style checks on elements that render target-script text
  for (const el of targetOwners) {
    const cs = getComputedStyle(el);
    const fs = parseFloat(cs.fontSize);
    const lh = cs.lineHeight === "normal" ? fs * 1.5 : parseFloat(cs.lineHeight);
    const ratio = lh / fs;
    const clipsY = ["hidden", "clip"].includes(cs.overflowY) || ["hidden", "clip"].includes(cs.overflow);
    const clipsX = ["hidden", "clip"].includes(cs.overflowX) || ["hidden", "clip"].includes(cs.overflow);

    // 3. Clipped text. Distinguish the Lao bug (part of a line cut: marks/vowels lost) from
    //    deliberate truncation (whole lines hidden by a card/line-clamp, or a one-line ellipsis).
    const overY = el.scrollHeight - el.clientHeight;
    const clamped = (cs.webkitLineClamp && cs.webkitLineClamp !== "none") || cs.textOverflow === "ellipsis";
    if (clipsY && overY > 1 && overY < lh * 0.9 && !clamped) {
      add("text_clipped", "high", el, {
        scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, cutPx: overY, lineHeightPx: Math.round(lh),
        overflow: cs.overflow, why: "Part of a line is cut off: stacked vowels / tone marks are lost.",
      });
    } else if ((clipsY && overY >= lh * 0.9) || (clipsX && el.scrollWidth > el.clientWidth + 1) || (clipsY && overY > 1 && clamped)) {
      add("text_truncated", "low", el, {
        scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
        scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, overflow: cs.overflow,
        why: "Whole lines / line end hidden (excerpt, line-clamp or ellipsis). Usually deliberate; not counted as a Lao defect.",
      });
    } else if (clipsY && (() => { const sp = inkSpill(el, cs); return sp.top > 1 || sp.bottom > 1; })()) {
      // Layout says it fits, but glyph ink (stacked vowels / tone marks) pokes outside an
      // overflow:hidden box. scrollHeight cannot see this: the classic clipped-tone-mark bug.
      const sp = inkSpill(el, cs);
      add("text_clipped", "high", el, {
        inkSpillTopPx: Math.round(sp.top * 10) / 10, inkSpillBottomPx: Math.round(sp.bottom * 10) / 10,
        boxHeightPx: el.clientHeight, overflow: cs.overflow,
        why: "Tone marks / vowels extend beyond a fixed-height overflow:hidden box and are cut off.",
      });
    } else if (cs.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1) {
      add("text_truncated", "low", el, { ellipsis: true });
    }

    // 4. Line height too tight for stacked diacritics
    if (ratio < 1.4) {  // Bootstrap's 1.428 passes; Latin-tuned 1.1-1.3 does not
      add("tight_line_height", ratio < 1.25 ? "high" : "medium", el, {
        lineHeightPx: Math.round(lh * 10) / 10, fontSizePx: fs, ratio: Math.round(ratio * 100) / 100,
        why: "Lao/Thai stack vowels and tone marks above and below the baseline; < ~1.5 overlaps or clips them.",
      });
    }

    // 5. Letter-spacing splits combining marks from their base consonant
    const ls = cs.letterSpacing === "normal" ? 0 : parseFloat(cs.letterSpacing);
    if (Math.abs(ls) > 0.5) add("letter_spacing", "medium", el, { letterSpacingPx: ls });

    // 6. Mid-syllable breaking (Lao/Thai/Khmer/Myanmar have no spaces between words)
    if (cs.wordBreak === "break-all" || cs.lineBreak === "anywhere") {
      add("syllable_break", "medium", el, { wordBreak: cs.wordBreak, lineBreak: cs.lineBreak });
    }
  }

  // 7. Font coverage: does the primary font actually contain the script?
  // If the first family lacks the glyphs, rendering falls through to whatever the device has.
  // Trick: measure with two different fallbacks; identical widths => the primary font drew it.
  const fonts = {};
  if (sentinels && sentinels.length === 2) {
    const ctx = document.createElement("canvas").getContext("2d");
    const w = (fam) => { ctx.font = `40px ${fam}`; return ctx.measureText(SAMPLE[script]).width; };
    const sentinelOk = Math.abs(w(`"${sentinels[0]}"`) - w(`"${sentinels[1]}"`)) > 0.5;
    const GENERIC = ["serif", "sans-serif", "monospace", "system-ui", "cursive", "fantasy", "ui-sans-serif", "ui-serif", "ui-monospace", "-apple-system", "blinkmacsystemfont"];
    const loadedWebfonts = new Set([...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family.replace(/["']/g, "").toLowerCase()));
    const covers = (family) => Math.abs(w(`"${family}", "${sentinels[0]}"`) - w(`"${family}", "${sentinels[1]}"`)) < 0.5;
    for (const el of targetOwners) {
      const fam = getComputedStyle(el).fontFamily;
      if (fonts[fam]) { fonts[fam].elements++; continue; }
      const stack = fam.split(",").map((s) => s.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
      const primary = stack[0] || "";
      let coveredBy = null;
      if (sentinelOk) {
        // first family in the declared stack that actually draws the script (generic keywords = device default)
        for (const f of stack) {
          if (GENERIC.includes(f.toLowerCase())) break;
          if (covers(f)) { coveredBy = f; break; }
        }
      }
      const webfont = coveredBy ? loadedWebfonts.has(coveredBy.toLowerCase()) : false;
      fonts[fam] = { primary, generic: GENERIC.includes(primary.toLowerCase()), covers: sentinelOk ? !!coveredBy : null,
                     coveredBy, webfont, elements: 1, el };
    }
    for (const [fam, info] of Object.entries(fonts)) {
      if (info.covers === false) {
        add("font_fallback", "high", info.el, {
          fontFamily: fam, primary: info.primary, coveredBy: null, shipsWebfont: false, elements: info.elements,
          why: "No font in the page's font stack contains this script, so each visitor sees whatever their device has (or tofu boxes).",
        });
      } else if (info.covers && !info.webfont) {
        add("font_fallback", "medium", info.el, {
          fontFamily: fam, primary: info.primary, coveredBy: info.coveredBy, shipsWebfont: false, elements: info.elements,
          why: `Lao is drawn by "${info.coveredBy}", which is installed on this machine but not shipped as a webfont; phones without it fall back.`,
        });
      }
      delete info.el;
    }
  }

  // Same-origin links for the planner
  const links = [...document.querySelectorAll("a[href]")]
    .map((a) => ({ href: a.href, text: (a.innerText || "").trim().slice(0, 60) }))
    .filter((l) => { try { return new URL(l.href).origin === location.origin && !l.href.includes("#"); } catch { return false; } })
    .filter((l, i, arr) => arr.findIndex((x) => x.href === l.href) === i)
    .slice(0, 40);

  const ocrBlocks = targetOwners
    .filter((el) => countTarget(ownText(el)) >= 6)
    .slice(0, 8)
    .map((el) => {
      const r = el.getBoundingClientRect();
      return { text: ownText(el).trim().replace(/\s+/g, " "), bbox: { x: Math.round(r.x + scrollX), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height) } };
    });

  const extra = [...document.querySelectorAll("[alt],[title],[aria-label],meta[content]")]
    .map((e) => e.getAttribute("alt") || e.getAttribute("title") || e.getAttribute("aria-label") || e.getAttribute("content") || "")
    .join(" | ");
  return {
    pageText: ((document.body ? document.body.textContent : "") + " | " + extra).replace(/\s+/g, " ").slice(0, 20000),
    title: document.title,
    htmlLang,
    scriptShare: Math.round(share * 100) / 100,
    targetElements: targetOwners.length,
    fonts,
    findings,
    links,
    ocrBlocks,
    pageHeight: document.documentElement.scrollHeight,
  };
}
