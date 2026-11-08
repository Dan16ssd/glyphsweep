"""Cut the real screen recording into per-scene clips that exactly fill each narrated scene.

    python video/cut_clips.py rec/<recording>.webm rec/marks.json
Writes public/clip-<scene>.mp4 and public/clips.json (segment speeds for the on-screen speed badge).
Facts shown in callouts are read from the recording's own UI and kept in FACTS below.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PUB = HERE / "public"
rec, marks_path = sys.argv[1], sys.argv[2]
rec_approve = sys.argv[3] if len(sys.argv) > 3 else None  # short recording of the approval click
M = json.load(open(marks_path, encoding="utf-8"))["marks"]
TL = {s["id"]: s for s in json.load(open(PUB / "timeline.json"))["scenes"]}
FACTS = json.load(open(HERE / "facts.json", encoding="utf-8")) if (HERE / "facts.json").exists() else {}


def m(k):
    if k not in M:
        raise SystemExit(f"missing mark {k}; have {list(M)}")
    return M[k]


# scene -> list of (start, end, share of scene duration, label)
# Tab times in VIDEO seconds. The webm drifts behind wall-clock marks (frames stall while the
# VM is busy), so these were found by matching each saved screenshot against the video frames.
VT = {"contain": 629.0, "findings": 647.0, "device": 662.0, "shots": 681.5, "patch": 695.5, "end": 701.3}
PLAN = {
    "05-demo": [(m("demo_click") - 0.5, m("ev21:report") + 2.5, 0.42, "agent working: plan → sandbox → verify → fix → prove"),
                (VT["contain"], VT["findings"] - 0.5, 0.58, "Containment tab")],
    "06-findings": [(VT["findings"], VT["device"] - 0.5, 1.0, "Findings tab")],
    "07-proof": [(VT["device"], VT["shots"] - 0.5, 0.6, "Bare device + OCR tab"),
                 (VT["shots"], VT["patch"] - 0.5, 0.4, "Before / after tab")],
    "08-trust": [(m("ev21:report") + 1.0, m("ev21:report") + 8.0, 0.35, "Timeline + score"),
                 (VT["patch"], VT["end"], 0.65, "Fix tab: proven patch")],
}

SRC = {sid: rec for sid in PLAN}
if rec_approve:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", rec_approve],
                       capture_output=True, text=True, check=True)
    PLAN["085-approve"] = [(2.6, 2.6 + TL["085-approve"]["duration"], 1.0, "Human approval")]  # real time: the click lands on "clicks approve"
    SRC["085-approve"] = rec_approve

out = {}
for sid, segs in PLAN.items():
    D = TL[sid]["duration"]
    parts, meta, at = [], [], 0.0
    for i, (a, b, share, label) in enumerate(segs):
        target = D * share
        real = b - a
        speed = max(real / target, 0.75)
        played = real / speed
        pad = max(0.0, target - played)
        f = (f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{speed:.4f},fps=30,"
             f"scale=1340:754:flags=lanczos,setsar=1,tpad=stop_mode=clone:stop_duration={pad + 0.05:.3f},"
             f"trim=duration={target:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f)
        meta.append({"at": round(at, 3), "dur": round(target, 3), "speed": round(speed, 2), "label": label})
        at += target
    fc = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[out]"
    dst = PUB / f"clip-{sid}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", SRC[sid], "-filter_complex", fc, "-map", "[out]", "-c:v", "libx264",
                    "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", str(dst)], check=True)
    out[sid] = {"segs": meta, "facts": FACTS.get(sid, {})}
    print(sid, [(s["label"][:20], s["speed"]) for s in meta])
json.dump(out, open(PUB / "clips.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
