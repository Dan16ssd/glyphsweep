# Southeast Asian script rendering scan

We ran GlyphSweep's deterministic detectors on **144 live websites** in four complex Southeast Asian scripts (government, banks, universities, telecoms, e-commerce, news). Homepage only, desktop (1280px) and phone (390px) width, read-only, rendered in the same Chromium + Noto font image the live agent uses, from a Vultr VM in Singapore, November 2026.

## Headline

- **51%** of all 144 sites have at least one *visible* rendering problem (pixel-verified clipping, no font that can draw the script, or words broken mid-syllable).
- **45%** never deliver a font for their own script: the text renders in whatever the visitor's device happens to have.
- **49%** don't declare the right `lang`, so screen readers pick the wrong voice and browsers the wrong line-breaking.

## By script

| | Lao (ພາສາລາວ) | Thai (ภาษาไทย) | Khmer (ភាសាខ្មែរ) | Burmese (မြန်မာဘာသာ) |
|---|---|---|---|---|
| Sites with real script content | 82 of 92 scanned | 24 of 48 scanned | 19 of 40 scanned | 19 of 38 scanned |
| **Visible rendering problem** | **50%** | **38%** | **63%** | **74%** |
| No font delivered for the script | 45% | 29% | 47% | 74% |
| Missing / wrong `lang` | 63% | 12% | 42% | 37% |
| Clipped marks (pixel-verified) | 2% | 0% | 16% | 0% |
| Mid-syllable breaks | 4% | 8% | 5% | 0% |
| *Risk:* line height too tight for stacked marks | 87% | 79% | 89% | 79% |
| *Risk:* letter-spacing on the script | 21% | 8% | 11% | 16% |
| Untranslated English UI | 76% | 71% | 74% | 84% |
| Median readiness score (worst viewport) | 61 | 72 | 61 | 61 |

## Notes and limits

- Detectors are heuristics. Clipping only counts when a screenshot changes after forcing `overflow: visible` (pixel-verified).
- "No font delivered" means no family in the page's font stack is both available and able to draw the script; generic keywords (`sans-serif`) count as "device default". Most flagged sites declare only Latin fonts (Arial, Poppins, Georgia...); a minority name a font that local PCs usually have but phones and foreign devices don't (Phetsarath OT in Laos, Pyidaungsu / Myanmar3 in Myanmar) without shipping it.
- Site lists were assembled by hand from well-known public sites per country; sites that didn't load from Singapore, sat behind a bot wall (common for Thai banks and government sites), or served too little script text are excluded (see "of N scanned").
- Burmese: 0 site(s) still name the legacy Zawgyi font. Zawgyi text is not standard Unicode, so it is a separate, deeper problem than rendering.
- Per-site results: `results/scan_<script>.jsonl`. Reproduce: `research/run_scans.sh` on the VM.
