"""Clean narration with a Microsoft neural voice (edge-tts), one WAV per narration.json entry.

    python video/gen_voice_edge.py [voice] [rate]
Writes video/public/vo/<id>.wav (overwrites). Default voice en-US-AndrewMultilingualNeural.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts

HERE = Path(__file__).parent
OUT = HERE / "public" / "vo"
OUT.mkdir(parents=True, exist_ok=True)
VOICE = sys.argv[1] if len(sys.argv) > 1 else "en-US-AndrewMultilingualNeural"
RATE = sys.argv[2] if len(sys.argv) > 2 else "+0%"


async def main():
    for item in json.load(open(HERE / "narration.json", encoding="utf-8")):
        mp3 = OUT / f"{item['id']}.mp3"
        for attempt in range(5):
            try:
                await edge_tts.Communicate(item["text"], VOICE, rate=RATE).save(str(mp3))
                break
            except edge_tts.exceptions.NoAudioReceived:
                await asyncio.sleep(3 * (attempt + 1))
        else:
            raise SystemExit(f"no audio for {item['id']}")
        wav = OUT / f"{item['id']}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav)], check=True)
        mp3.unlink()
        print(wav.name, flush=True)


asyncio.run(main())
