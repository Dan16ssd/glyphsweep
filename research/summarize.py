"""Turn scan.jsonl into the headline numbers for the paper / press release.

    python research/summarize.py --in research/results/scan.jsonl --md research/results/summary.md
"""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK_NAMES = {
    "text_clipped": "Lao text cut off (tone marks / vowels clipped), pixel-verified",
    "tight_line_height": "Line height too tight for Lao stacked marks",
    "font_fallback": "No Lao font delivered (device fallback)",
    "html_lang": "Missing or wrong lang=\"lo\"",
    "syllable_break": "Words broken mid-syllable",
    "letter_spacing": "Letter-spacing pulls marks off consonants",
    "untranslated": "Untranslated English UI text",
    "text_truncated": "Deliberate truncation (excerpt / ellipsis), not a defect",
}


def load(path, min_lao):
    sites = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        views = r.get("views") or {}
        ok = {k: v for k, v in views.items() if not v.get("error") and v.get("findings") is not None}
        if not ok:
            continue
        if max(v.get("lao_chars", 0) for v in ok.values()) < min_lao:
            continue  # not really a Lao-language page once rendered
        r["ok_views"] = ok
        sites.append(r)
    return sites


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=os.path.join(HERE, "results", "scan.jsonl"))
    ap.add_argument("--md", default=os.path.join(HERE, "results", "summary.md"))
    ap.add_argument("--csv", default=os.path.join(HERE, "results", "per_site.csv"))
    ap.add_argument("--min-lao", type=int, default=100)
    a = ap.parse_args()

    total_lines = sum(1 for _ in open(a.inp, encoding="utf-8"))
    sites = load(a.inp, a.min_lao)
    n = len(sites)
    L = [f"# Lao web rendering scan\n", f"Scanned {total_lines} sites; **{n}** rendered successfully with Lao content "
         f"(>= {a.min_lao} Lao characters).\n"]
    if not n:
        open(a.md, "w", encoding="utf-8").write("\n".join(L))
        print("\n".join(L))
        return

    # site-level: a site "has" a problem if either viewport shows it
    has = defaultdict(set)
    per_cat = defaultdict(list)
    rows = []
    for s in sites:
        checks = set()
        for v in s["ok_views"].values():
            checks |= {f["check"] for f in v["findings"] if f["check"] != "text_clipped" or f.get("verified")}
        for c in checks:
            has[c].add(s["host"])
        sc = {k: v.get("score") for k, v in s["ok_views"].items()}
        worst = min(x for x in sc.values() if x is not None)
        per_cat[s.get("category") or "?"].append(worst)
        rows.append({"host": s["host"], "category": s.get("category"), "desktop_score": sc.get("desktop"),
                     "phone_score": sc.get("phone"), "problems": ";".join(sorted(checks)),
                     "html_lang": (s["ok_views"].get("desktop") or next(iter(s["ok_views"].values()))).get("html_lang")})

    # visible defects (what a reader actually sees) vs risk factors (CSS that often causes them)
    hard_font = set()
    langs = Counter()
    for s in sites:
        v0 = s["ok_views"].get("desktop") or next(iter(s["ok_views"].values()))
        langs[(v0.get("html_lang") or "(missing)").lower()] += 1
        for v in s["ok_views"].values():
            if any(f["check"] == "font_fallback" and f["severity"] == "high" for f in v["findings"]):
                hard_font.add(s["host"])
    any_render = has["text_clipped"] | hard_font | has["syllable_break"]
    L.append("## Headline\n")
    L.append(f"- **{pct(len(any_render), n)}** of Lao websites ({len(any_render)}/{n}) have at least one visible "
             f"Lao *rendering* problem.")
    L.append(f"- **{pct(len(has['text_clipped']), n)}** cut off Lao text (clipped tone marks or vowels).")
    L.append(f"- **{pct(len(has['font_fallback']), n)}** never deliver a Lao font (no font in the stack that the page ships or the "
             f"browser has can draw Lao), so Lao text renders in whatever the visitor's device happens to have.")
    L.append(f"- **{pct(len(has['html_lang']), n)}** do not declare the page as Lao (lang=\"lo\").\n")

    L.append("## Problems by type (share of sites)\n")
    L.append("| Problem | Sites | Share |\n|---|---|---|")
    for c, name in CHECK_NAMES.items():
        L.append(f"| {name} | {len(has[c])} | {pct(len(has[c]), n)} |")

    L.append("\n## Readiness score by category (worst of desktop/phone, 100 = no problems)\n")
    L.append("| Category | Sites | Median | Mean |\n|---|---|---|---|")
    for cat, xs in sorted(per_cat.items(), key=lambda kv: -len(kv[1])):
        L.append(f"| {cat} | {len(xs)} | {median(xs):.0f} | {mean(xs):.0f} |")

    d_only = p_only = 0
    for s in sites:
        v = s["ok_views"]
        if "desktop" in v and "phone" in v:
            keep = lambda fs: {f["check"] for f in fs if f["check"] != "text_clipped" or f.get("verified")}
            dc, pc = keep(v["desktop"]["findings"]), keep(v["phone"]["findings"])
            d_only += bool(dc - pc)
            p_only += bool(pc - dc)
    L.append(f"\n## Desktop vs phone\n\n- Sites with a problem that only appears on phone width: {p_only}\n"
             f"- Only on desktop width: {d_only}\n")

    fonts = Counter()
    for s in sites:
        for f in (s["ok_views"].get("desktop") or {}).get("fonts") or []:
            fonts[f if isinstance(f, str) else json.dumps(f, ensure_ascii=False)[:60]] += 1
    if fonts:
        L.append("## Most common fonts on Lao text\n")
        L.extend(f"- {k}: {v}" for k, v in fonts.most_common(10))

    os.makedirs(os.path.dirname(a.md), exist_ok=True)
    open(a.md, "w", encoding="utf-8").write("\n".join(L) + "\n")
    with open(a.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["category"] or "", r["host"])))
    print("\n".join(L))


if __name__ == "__main__":
    main()
