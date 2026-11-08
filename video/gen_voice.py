"""Narration in Danny's cloned voice (F5-TTS, reference clip from the AMD pitch).

    Desktop/AMD/.venv-tts/Scripts/python video/gen_voice.py
Writes video/public/vo/<id>.wav, one per narration.json entry.
"""
import json
from pathlib import Path

from f5_tts.api import F5TTS

HERE = Path(__file__).parent
REF = Path(r"C:\Users\Danny\Desktop\AMD\pitch-audio\voice-ref-short.wav")
REF_TEXT = "Hey there! I'm currently recording this short clip to train my AI voice model."
OUT = HERE / "public" / "vo"
OUT.mkdir(parents=True, exist_ok=True)

f5 = F5TTS()
for item in json.load(open(HERE / "narration.json", encoding="utf-8")):
    dest = OUT / f"{item['id']}.wav"
    if dest.exists():
        continue
    wav, sr, _ = f5.infer(ref_file=str(REF), ref_text=REF_TEXT, gen_text=item["text"],
                          file_wave=str(dest), seed=7, remove_silence=True)
    print(f"{dest.name}: {len(wav) / sr:.1f}s", flush=True)
print("done")
