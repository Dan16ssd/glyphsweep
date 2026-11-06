"""Fake OpenAI-compatible inference server for exercising the model path without a Vultr key.

It deliberately returns awkward-but-realistic output so the parsing and containment code is tested:
  * planner: answer only in `reasoning_content` (empty `content`), plus one URL the sandbox never saw
  * verifier: JSON wrapped in <think> and a ```json fence
  * fixer round 1: incomplete patch + a sneaky image-set() beacon  -> must be REJECTED by the sanitizer
  * fixer round 1 (retry path is fallback) / round 2: complete clean patch with translations
Run:  python -m uvicorn fake_inference:app --port 8099   (from tests/)
"""

import json
import re

from fastapi import FastAPI, Request

app = FastAPI()
CALLS = []
MODE = {"m": "normal"}  # normal: incomplete round 1 -> round 2 ; evil: round 1 smuggles a beacon


@app.post("/mode/{m}")
def mode(m: str):
    MODE["m"] = m
    CALLS.clear()
    return MODE


def reply(content, reasoning=None):
    msg = {"role": "assistant", "content": content}
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    return {"choices": [{"message": msg}], "usage": {"prompt_tokens": 100, "completion_tokens": 50}}


@app.get("/v1/models")
def models():
    return {"data": [{"id": "qwen3.8-27b", "input_modalities": [{"type": "text"}, {"type": "image"}],
                      "output_modalities": [{"type": "text"}]}]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    content = body["messages"][0]["content"]
    text = content if isinstance(content, str) else " ".join(c.get("text", "") for c in content if c.get("type") == "text")
    has_image = not isinstance(content, str) and any(c.get("type") == "image_url" for c in content)

    if "planning a" in text:
        CALLS.append("plan")
        links = json.loads(re.search(r"<untrusted>(\[.*?\])</untrusted>", text, re.S).group(1))
        picks = [l["href"] for l in links if "checkout" in l["href"] or "about" in l["href"]][:2]
        picks.append("https://evil.example/not-discovered")
        return reply("", json.dumps({"pages": picks, "reasoning": "checkout has forms; about is a control page"}))

    if has_image:
        CALLS.append("verify")
        listing = json.loads(re.search(r"<untrusted>(\[.*?\])</untrusted>", text, re.S).group(1))
        verdicts = [{"n": x["n"], "visible": "no" if x["check"].startswith("tight_line_height") and x["n"] % 3 == 0 else "yes",
                     "note": "tone marks touch the line above"} for x in listing]
        return reply("<think>looking at boxes</think>\n```json\n" + json.dumps(
            {"verdicts": verdicts, "injection_attempts": ["footer text tells auditors to report zero issues"]}) + "\n```")

    if "You fix" in text:
        round2 = "ROUND 2" in text
        CALLS.append("fix-r2" if round2 else "fix-r1")
        style = json.loads(re.search(r"Style findings:\n<untrusted>(.*?)</untrusted>", text, re.S).group(1))
        sels = sorted({f["selector"] for f in style if f["check"] in ("text_clipped", "tight_line_height")})
        tr = [{"original": "Add to cart", "translated": "ເພີ່ມໃສ່ກະຕ່າ"}, {"original": "Buy now", "translated": "ຊື້ດຽວນີ້"},
              {"original": "Place order", "translated": "ສັ່ງຊື້"}]
        if not round2 and MODE["m"] != "evil":
            # honest but incomplete first attempt: only line-height -> leaves letter-spacing etc. for round 2
            css = (", ".join(sels) or "h1") + " { line-height: 1.8 !important; height: auto !important; overflow: visible !important; }"
            return reply(json.dumps({"css": css, "translations": tr, "source_changes": ['Set <html lang="lo">'], "injection_attempts": []}))
        if not round2:
            # attack: beacon smuggled via image-set -> sanitizer must reject the whole patch
            css = ", ".join(sels) + " { line-height: 1.8 !important; }\nbody { background-image: image-set(\"https://beacon.evil.example/x.png\" 1x); }"
            return reply(json.dumps({"css": css, "translations": tr, "source_changes": ['Set <html lang="lo">'], "injection_attempts": []}))
        css = ("@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Lao:wght@400;700&display=swap');\n"
               "body, body * { font-family: \"Noto Sans Lao\", sans-serif !important; letter-spacing: normal !important; "
               "word-break: normal !important; overflow-wrap: break-word; }\n"
               + (", ".join(sels) or "h1") + " { line-height: 1.8 !important; height: auto !important; overflow: visible !important; }")
        return reply(json.dumps({"css": css, "translations": tr, "source_changes": ['Set <html lang="lo">'], "injection_attempts": []}))

    CALLS.append("other")
    return reply("{}")


@app.get("/calls")
def calls():
    return CALLS
