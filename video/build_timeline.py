"""Stitch the cloned-voice sections into one track and time everything off the real audio.

    python video/build_timeline.py
public/vo/*.wav -> public/narration.wav, public/timeline.json (scene start/duration),
public/captions.json (word timings from faster-whisper, Remotion Caption format), out/glyphsweep.srt
"""
import json
import subprocess
from pathlib import Path

from faster_whisper import WhisperModel

HERE = Path(__file__).parent
PUB = HERE / "public"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
GAP = 0.7          # silence after each section
LEAD = 0.6         # silence before the first word
TAIL = 4.0         # end card hold
ITEMS = json.load(open(HERE / "narration.json", encoding="utf-8"))


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


scenes, t, inputs, filt = [], 0.0, [], []
for i, it in enumerate(ITEMS):
    wav = PUB / "vo" / f"{it['id']}.wav"
    d = dur(wav)
    lead = LEAD if i == 0 else 0
    tail = TAIL if i == len(ITEMS) - 1 else GAP
    scenes.append({"id": it["id"], "start": round(t, 3), "duration": round(lead + d + tail, 3), "voice": round(t + lead, 3)})
    inputs += ["-i", str(wav)]
    filt.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono,adelay={int((t + lead) * 1000)}[a{i}]")
    t += lead + d + tail
total = round(t, 3)
filt.append("".join(f"[a{i}]" for i in range(len(ITEMS))) + f"amix=inputs={len(ITEMS)}:normalize=0,apad,atrim=0:{total},loudnorm=I=-16:TP=-1.5[out]")
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]", "-ar", "44100",
                str(PUB / "narration.wav")], check=True)
json.dump({"total": total, "scenes": scenes}, open(PUB / "timeline.json", "w"), indent=1)
print(f"total {total:.1f}s")
for s in scenes:
    print(f"  {s['id']:12s} {s['start']:6.1f} +{s['duration']:5.1f}")

model = WhisperModel("small.en", device="cpu", compute_type="int8")
import difflib
import re as _re

norm = lambda w: _re.sub(r"[^a-z0-9]", "", w.lower())
caps = []
# Captions show the exact script text; Whisper (run per section) only supplies the timing.
for sc, it in zip(scenes, ITEMS):
    segs, _ = model.transcribe(str(PUB / "vo" / f"{sc['id']}.wav"), word_timestamps=True, language="en",
                               condition_on_previous_text=False)
    heard = [w for s_ in segs for w in s_.words]
    words = it["text"].split()
    off = sc["voice"] * 1000
    times = [None] * len(words)
    sm = difflib.SequenceMatcher(a=[norm(w) for w in words], b=[norm(w.word) for w in heard], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            h = heard[blk.b + k]
            times[blk.a + k] = (h.start * 1000, h.end * 1000)
    end_all = (heard[-1].end * 1000) if heard else 1000
    # fill unmatched words by interpolating between known neighbours
    i = 0
    while i < len(words):
        if times[i] is None:
            j = i
            while j < len(words) and times[j] is None:
                j += 1
            t0 = times[i - 1][1] if i > 0 else 0
            t1 = times[j][0] if j < len(words) else end_all
            step = (t1 - t0) / (j - i)
            for k in range(i, j):
                times[k] = (t0 + step * (k - i), t0 + step * (k - i + 1))
            i = j
        else:
            i += 1
    for w, (t0, t1) in zip(words, times):
        caps.append({"text": " " + w, "startMs": round(off + t0), "endMs": round(off + t1),
                     "timestampMs": round(off + t0), "confidence": 1})
json.dump(caps, open(PUB / "captions.json", "w"), indent=0)


def srt(x):
    ms = round(x * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


lines, cur = [], []
for w in caps:
    cur.append(w)
    if w["text"].strip()[-1:] in ".?!" or len(cur) >= 10:
        lines.append(cur)
        cur = []
if cur:
    lines.append(cur)
with open(OUT / "glyphsweep.srt", "w", encoding="utf-8") as f:
    for i, l in enumerate(lines, 1):
        f.write(f"{i}\n{srt(l[0]['startMs'] / 1000)} --> {srt(l[-1]['endMs'] / 1000)}\n{''.join(w['text'] for w in l).strip()}\n\n")
print(len(caps), "words")
