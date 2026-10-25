"""Net ID tags (QR codes) and staged evidence photos.

The QR payload is the only source of a claim's net identity:
    GEARTAG|<chainId>|<escrow address>|<netId>|<checksum>
The checksum catches misreads and tags for a different deployment; it is not a security feature
(QR codes can be copied, which is why verification has further checks).
"""
import io
import math
import random

import cv2
import numpy as np
import qrcode
from eth_utils import keccak
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from engine import config as C

EVIDENCE_DIR = C.ROOT / "engine" / "assets" / "evidence"
# base photo -> (x range, y range) for the tag's top-left corner as fractions of the image, and tag width fraction
BASE_PHOTOS = {
    "derelict_net_coral.jpg": ((0.40, 0.52), (0.44, 0.50), 0.14),
    "net_pile_dutch_harbor.jpg": ((0.42, 0.55), (0.40, 0.48), 0.16),
    "monster_net_pearl_hermes.jpg": ((0.24, 0.34), (0.34, 0.42), 0.16),
}


def _checksum(chain_id, escrow, net_id):
    return keccak(f"{chain_id}|{escrow.lower()}|{net_id}".encode())[:4].hex()


def payload(chain_id, escrow, net_id):
    return f"GEARTAG|{chain_id}|{escrow}|{net_id}|{_checksum(chain_id, escrow, net_id)}"


def parse(text, chain_id, escrow):
    """Return the net ID, or raise ValueError with a human-readable reason."""
    parts = (text or "").split("|")
    if len(parts) != 5 or parts[0] != "GEARTAG":
        raise ValueError("QR code found, but it is not a gear passport tag")
    _, cid, addr, nid, chk = parts
    if not nid.isdigit() or chk != _checksum(int(cid), addr, int(nid)):
        raise ValueError("tag checksum does not match (misread or altered tag)")
    if int(cid) != chain_id or addr.lower() != escrow.lower():
        raise ValueError("tag belongs to a different registry deployment")
    return int(nid)


def _font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tag_image(chain_id, escrow, net_id, owner_label=""):
    """A printable yellow gear tag with the QR code and the human-readable ID."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(payload(chain_id, escrow, net_id)); qr.make(fit=True)
    q = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w = q.width + 60
    tag = Image.new("RGB", (w, q.height + 150), (250, 204, 21))
    tag.paste(q, (30, 30))
    d = ImageDraw.Draw(tag)
    d.text((w // 2, q.height + 62), f"NET #{net_id:04d}", fill="black", font=_font(44), anchor="mm")
    d.text((w // 2, q.height + 112), owner_label or "GEAR PASSPORT", fill=(40, 40, 40), font=_font(22), anchor="mm")
    d.ellipse((w // 2 - 10, 8, w // 2 + 10, 24), fill=(60, 60, 60))     # lanyard hole
    return tag


def staged_photo(tag: Image.Image, variant="recovered", seed=0) -> Image.Image:
    """'recovered': the tag composited onto a public-domain photo of real netting.
    'printout':  the same tag printed on paper on a desk, with no gear (fraud test)."""
    rnd = random.Random(seed)
    if variant == "printout":
        img = Image.new("RGB", (1280, 900), (122, 86, 54))
        noise = np.random.default_rng(seed).normal(0, 9, (900, 1280, 1)).repeat(3, 2)
        img = Image.fromarray(np.clip(np.asarray(img, float) + noise, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
        paper = Image.new("RGB", (620, 800), (246, 246, 242))
        t = tag.resize((420, int(420 * tag.height / tag.width)))
        paper.paste(t, (100, 90))
        paper = paper.rotate(rnd.uniform(-6, 6), expand=True, fillcolor=(122, 86, 54))
        img.paste(paper, (330, 40))
        return img
    name = list(BASE_PHOTOS)[seed % len(BASE_PHOTOS)]
    (x0, x1), (y0, y1), size = BASE_PHOTOS[name]
    base = Image.open(EVIDENCE_DIR / name).convert("RGB")
    img = base.resize((1280, int(base.height * 1280 / base.width)))
    tw = int(img.width * size)
    t = tag.resize((tw, int(tw * tag.height / tag.width))).convert("RGBA")
    t = t.rotate(rnd.uniform(-10, 10), expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", t.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 110), mask=t.split()[3])
    x = int(img.width * rnd.uniform(x0, x1)); y = int(img.height * rnd.uniform(y0, y1))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(6)), (x + 8, y + 10), shadow)
    img.paste(t, (x, y), t)
    return img


def to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=90); return buf.getvalue()


def decode(image_bytes: bytes):
    """Find and decode a QR code in a photo. Returns the text or None."""
    arr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    det = cv2.QRCodeDetector()
    for img in (arr, cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)):
        for scale in (1.0, 0.5, 1.5):
            im = img if scale == 1.0 else cv2.resize(img, None, fx=scale, fy=scale)
            text, pts, _ = det.detectAndDecode(im)
            if text:
                return text
    return None
