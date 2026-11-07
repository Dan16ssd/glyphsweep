"""Cross-script summary: Lao, Thai, Khmer, Burmese scans side by side.

    python research/compare.py            # reads research/results/scan_<script>.jsonl
writes research/RESULTS.md and research/results/compare.json (used by the website).

Definitions (same for every script):
  site counted     = rendered without error and has >= MIN_CHARS characters of the script
  visible problem  = pixel-verified clipping, OR no font in the stack can draw the script (high
                     font_fallback), OR words broken mid-syllable
  no font          = high font_fallback (page neither ships nor names an available font for the script)
  wrong lang       = html_lang finding (missing / wrong lang attribute)
"""

import json
import os
from collections import defaultdict
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
MIN_CHARS = 100
SCRIPTS = [("lao", "Lao", "ພາສາລາວ", "lo", "Laos", 7.5), ("thai", "Thai", "ภาษาไทย", "th", "Thailand", 70),
           ("khmer", "Khmer", "ភាសាខ្មែរ", "km", "Cambodia", 17), ("myanmar", "Burmese", "မြန်မာဘာသာ", "my", "Myanmar", 54)]
RISK = ["tight_line_height", "letter_spacing", "untranslated"]


def load(script):
    p = os.path.join(RES, f"scan_{script}.jsonl")
    if not os.path.exists(p):
        return [], 0
    sites, total = [], 0
    for line in open(p, encoding="utf-8"):
        total += 1
        r = json.loads(line)
        ok = {k: v for k, v in (r.get("views") or {}).items() if not v.get("error") and v.get("findings") is not None}
        if ok and max(v.get("script_chars", v.get("lao_chars", 0)) for v in ok.values()) >= MIN_CHARS:
            r["ok"] = ok
            sites.append(r)
    return sites, total


def analyse(sites):
    has = defaultdict(set)
    worst, zawgyi = [], set()
    for s in sites:
        for v in s["ok"].values():
            for f in v["findings"]:
                if f["check"] == "text_clipped" and not f.get("verified"):
                    continue
                key = "font_hard" if f["check"] == "font_fallback" and f["severity"] == "high" else f["check"]
                has[key].add(s["host"])
            if any("zawgyi" in (str(ff) or "").lower() for ff in (v.get("fonts") or [])):
                zawgyi.add(s["host"])
        worst.append(min(v["score"] for v in s["ok"].values() if v.get("score") is not None))
    visible = has["text_clipped"] | has["font_hard"] | has["syllable_break"]
    n = len(sites)
    pc = lambda x: round(100 * len(x) / n) if n else None
    return {"sites": n, "visible": pc(visible), "no_font": pc(has["font_hard"]), "wrong_lang": pc(has["html_lang"]),
            "clipped": pc(has["text_clipped"]), "syllable_break": pc(has["syllable_break"]),
            "tight_line_height": pc(has["tight_line_height"]), "letter_spacing": pc(has["letter_spacing"]),
            "untranslated": pc(has["untranslated"]), "zawgyi": len(zawgyi), "median_score": round(median(worst)) if worst else None,
            "counts": {"visible": len(visible), "no_font": len(has["font_hard"]), "wrong_lang": len(has["html_lang"])},
            "by_category": {c: sum(1 for s in sites if (s.get("category") or "?") == c) for c in {s.get("category") or "?" for s in sites}}}


def main():
    out, total_sites = {}, 0
    for key, name, native, lang, country, millions in SCRIPTS:
        sites, scanned = load(key)
        if not scanned:
            continue
        a = analyse(sites)
        a.update(name=name, native=native, lang=lang, country=country, readers_m=millions, scanned=scanned)
        out[key] = a
        total_sites += a["sites"]
    all_sites = [s for key, *_ in SCRIPTS for s in load(key)[0]]
    out["_all"] = analyse(all_sites) if all_sites else {}
    json.dump(out, open(os.path.join(RES, "compare.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    rows = [k for k, *_ in SCRIPTS if k in out]
    A = out["_all"]
    L = ["# Southeast Asian script rendering scan\n",
         f"We ran GlyphSweep's deterministic detectors on **{total_sites} live websites** in four complex Southeast Asian scripts "
         "(government, banks, universities, telecoms, e-commerce, news). Homepage only, desktop (1280px) and phone (390px) width, "
         "read-only, rendered in the same Chromium + Noto font image the live agent uses, from a Vultr VM in Singapore, November 2026.\n",
         "## Headline\n",
         f"- **{A['visible']}%** of all {A['sites']} sites have at least one *visible* rendering problem "
         "(pixel-verified clipping, no font that can draw the script, or words broken mid-syllable).",
         f"- **{A['no_font']}%** never deliver a font for their own script: the text renders in whatever the visitor's device happens to have.",
         f"- **{A['wrong_lang']}%** don't declare the right `lang`, so screen readers pick the wrong voice and browsers the wrong line-breaking.\n",
         "## By script\n",
         "| | " + " | ".join(f"{out[k]['name']} ({out[k]['native']})" for k in rows) + " |",
         "|---|" + "---|" * len(rows),
         "| Sites with real script content | " + " | ".join(f"{out[k]['sites']} of {out[k]['scanned']} scanned" for k in rows) + " |",
         "| **Visible rendering problem** | " + " | ".join(f"**{out[k]['visible']}%**" for k in rows) + " |",
         "| No font delivered for the script | " + " | ".join(f"{out[k]['no_font']}%" for k in rows) + " |",
         "| Missing / wrong `lang` | " + " | ".join(f"{out[k]['wrong_lang']}%" for k in rows) + " |",
         "| Clipped marks (pixel-verified) | " + " | ".join(f"{out[k]['clipped']}%" for k in rows) + " |",
         "| Mid-syllable breaks | " + " | ".join(f"{out[k]['syllable_break']}%" for k in rows) + " |",
         "| *Risk:* line height too tight for stacked marks | " + " | ".join(f"{out[k]['tight_line_height']}%" for k in rows) + " |",
         "| *Risk:* letter-spacing on the script | " + " | ".join(f"{out[k]['letter_spacing']}%" for k in rows) + " |",
         "| Untranslated English UI | " + " | ".join(f"{out[k]['untranslated']}%" for k in rows) + " |",
         "| Median readiness score (worst viewport) | " + " | ".join(str(out[k]['median_score']) for k in rows) + " |",
         "",
         "## Notes and limits\n",
         "- Detectors are heuristics. Clipping only counts when a screenshot changes after forcing `overflow: visible` (pixel-verified).",
         "- \"No font delivered\" means no family in the page's font stack is both available and able to draw the script; generic keywords (`sans-serif`) count as \"device default\". Most flagged sites declare only Latin fonts (Arial, Poppins, Georgia...); a minority name a font that local PCs usually have but phones and foreign devices don't (Phetsarath OT in Laos, Pyidaungsu / Myanmar3 in Myanmar) without shipping it.",
         "- Site lists were assembled by hand from well-known public sites per country; sites that didn't load from Singapore, sat behind a bot wall (common for Thai banks and government sites), or served too little script text are excluded (see \"of N scanned\").",
         ("- Burmese: " + (f"{out['myanmar']['zawgyi']} site(s) still name the legacy Zawgyi font. Zawgyi text is not standard Unicode, so it is a separate, deeper problem than rendering." if "myanmar" in out else "")),
         "- Per-site results: `results/scan_<script>.jsonl`. Reproduce: `research/run_scans.sh` on the VM.",
         ]
    open(os.path.join(HERE, "RESULTS.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
