"""Local AI scene check (free, offline): is physical fishing gear in the photo, or only a tag?

This is the one thing deterministic checks cannot tell: a photo of real netting with the tag on it
versus a photo of a copied tag (printout or screen). It is a model's opinion, not proof.
Runs on Ollama with a small vision-language model; if Ollama is unavailable the check reports
"not run" and the claim is flagged rather than passed.
"""
import json
import os
import time

MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:3b")

SCHEMA = {
    "type": "object",
    "properties": {
        "objects": {"type": "string"},
        "scene_type": {"type": "string", "enum": ["A_physical_fishing_gear", "B_tag_on_paper_card_or_screen_only",
                                                  "C_other_or_unclear"]},
        "confidence": {"type": "number"},
    },
    "required": ["objects", "scene_type", "confidence"],
}

# Multiple choice with a description first: small models answer this far more reliably than a list of
# yes/no fields (in testing, the yes/no version mistook the word "GEAR" printed on a tag for real gear).
PROMPT = """List the main physical objects in this photo in a few words (field "objects").
Then classify the photo (field "scene_type"):
A = real, physical fishing gear is in the scene (nets, ropes, lines, floats, traps), possibly with a tag attached.
B = the photo mainly shows a tag, label or QR code on paper, a card or a screen, and NO physical fishing gear.
C = anything else, or you cannot tell.
Words printed on a tag or paper do not count as fishing gear. Give your confidence from 0 to 1."""

MAX_SIDE = 512      # downscaling keeps a check at ~4-5 s on an M1 Pro (full-size photos took ~50 s)


def _small(image_bytes):
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def available():
    try:
        import ollama
        return any(m.model.startswith(MODEL.split(":")[0]) for m in ollama.list().models)
    except Exception:
        return False


def check(image_bytes: bytes) -> dict:
    """Returns the model's structured answer plus timing, or {'error': ...} if the model is unavailable."""
    try:
        import ollama
        t0 = time.time()
        r = ollama.chat(model=MODEL, format=SCHEMA, options={"temperature": 0},
                        messages=[{"role": "user", "content": PROMPT, "images": [_small(image_bytes)]}])
        out = json.loads(r.message.content)
        out["model"] = MODEL
        out["seconds"] = round(time.time() - t0, 1)
        return out
    except Exception as e:     # model missing, server down, malformed output
        return {"error": f"{type(e).__name__}: {e}", "model": MODEL}


def decide(ans: dict):
    """Map the model's answer to a check status: pass / flag / fail."""
    if "error" in ans:
        return "flag", "Local AI check did not run, so the claim needs a second look"
    conf = float(ans.get("confidence", 0))
    kind = ans.get("scene_type", "")
    seen = ans.get("objects", "")
    if kind.startswith("A") and conf >= 0.6:
        return "pass", f"Physical fishing gear in the photo (model saw: {seen})"
    if kind.startswith("B") and conf >= 0.6:
        return "fail", f"Only a tag on paper/screen, no physical gear (model saw: {seen})"
    return "flag", f"Model could not confirm physical gear (model saw: {seen}; confidence {conf:.2f})"
