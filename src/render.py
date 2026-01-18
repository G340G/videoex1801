import math
import random
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from .vhs import apply_vhs, to_grayscale


def _font(size: int):
    for name in ["DejaVuSansMono.ttf", "DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def letterbox(img: Image.Image, w: int, h: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((w, h))
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    x = (w - img.width) // 2
    y = (h - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def make_noise_plate(w: int, h: int) -> Image.Image:
    arr = np.random.randint(0, 255, size=(h, w), dtype=np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def ken_burns(img: Image.Image, w: int, h: int, t: float, rng: random.Random) -> Image.Image:
    """
    Slow creepy zoom/pan on the image. t in [0,1].
    """
    base = img.convert("RGB")
    # choose a stable-ish zoom track per clip
    z0 = 1.00
    z1 = 1.18 + rng.random() * 0.08
    z = z0 + (z1 - z0) * (0.5 - 0.5 * math.cos(math.pi * t))  # smooth
    # pan targets
    W, H = base.size
    cw = int(W / z)
    ch = int(H / z)
    cx0 = int((W - cw) * (0.15 + rng.random() * 0.2))
    cy0 = int((H - ch) * (0.15 + rng.random() * 0.2))
    cx1 = int((W - cw) * (0.65 + rng.random() * 0.2))
    cy1 = int((H - ch) * (0.65 + rng.random() * 0.2))
    cx = int(cx0 + (cx1 - cx0) * t)
    cy = int(cy0 + (cy1 - cy0) * t)
    crop = base.crop((cx, cy, cx + cw, cy + ch))
    crop = crop.resize((w, h), Image.NEAREST)
    return crop


def redact_line(s: str, rng: random.Random) -> str:
    """
    Make “scraped” text feel ARG-like: redactions and clipped phrases.
    """
    s = s.strip()
    if len(s) > 120:
        s = s[:120]
    if rng.random() < 0.35:
        # replace a chunk with blocks
        a = rng.randint(10, max(10, len(s)//2))
        b = min(len(s), a + rng.randint(8, 18))
        s = s[:a] + "█" * (b - a) + s[b:]
    # occasional tag prefix
    if rng.random() < 0.25:
        s = f"[{rng.randint(10,99)}.{rng.randint(10,99)}] {s}"
    return s


def overlay_vhs_osd(draw: ImageDraw.ImageDraw, w: int, h: int, meta: dict, cfg_overlay: dict, frame_idx: int, rng: random.Random, room_label: str):
    f_small = _font(16)
    f_med = _font(20)
    f_big = _font(26)

    # REC + dot
    draw.text((26, 18), "REC", font=f_big, fill=(235, 235, 235))
    draw.ellipse((10, 24, 22, 36), fill=(235, 235, 235))

    fps = meta["fps"]
    seconds = frame_idx / fps
    hh = int(seconds // 3600)
    mm = int((seconds % 3600) // 60)
    ss = int(seconds % 60)
    ff = int(frame_idx % fps)
    tc = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"
    draw.text((w - 200, 18), tc, font=f_med, fill=(235, 235, 235))

    seed_int = meta["theme"]["rng_int"]
    day = 1 + (seed_int % 28)
    month = 1 + ((seed_int // 31) % 12)
    year = 1992 + ((seed_int // 97) % 8)
    date = f"{day:02d}.{month:02d}.{year:04d}"

    loc = rng.choice(cfg_overlay.get("location_pool", ["UNKNOWN"]))
    cam = rng.choice(cfg_overlay.get("camera_pool", ["CAM"]))
    track = 18 + int(42 * (0.5 + 0.5 * math.sin(frame_idx * 0.03)))

    draw.text((24, h - 50), f"{date}  {loc}  {cam}", font=f_small, fill=(235, 235, 235))
    draw.text((w - 300, h - 50), f"TRK {track:02d}  SP", font=f_small, fill=(235, 235, 235))
    draw.text((24, 52), room_label, font=f_small, fill=(220, 220, 220))

    draw.rectangle((6, 6, w - 6, h - 6), outline=(90, 90, 90), width=2)


def glitch_errors(draw: ImageDraw.ImageDraw, w: int, h: int, rng: random.Random, brain: str):
    if rng.random() < 0.26:
        f = _font(18)
        msgs = [
            "ERROR: DROP FRAME",
            "SYNC LOST",
            "HEAD CLOG DETECTED",
            "RF INTERFERENCE",
            "TRACKING MISALIGN",
            "CARRIER DRIFT",
            f"{brain.upper()} EVENT FLAGGED",
            "FIELD ORDER SWAP",
        ]
        msg = rng.choice(msgs)
        x = rng.randint(40, max(41, w - 340))
        y = rng.randint(80, max(81, h - 120))
        draw.text((x, y), msg, font=f, fill=(235, 235, 235))


def draw_infographic(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, rng: random.Random, title: str):
    """
    Creepy nonsense chart panel (looks like a VHS-era diagnostic overlay).
    """
    f_t = _font(16)
    f_s = _font(14)
    d.rectangle((x, y, x + w, y + h), outline=(180, 180, 180), width=2)
    d.text((x + 10, y + 8), title, font=f_t, fill=(235, 235, 235))

    # axes
    ax_y0 = y + 32
    ax_y1 = y + h - 12
    ax_x0 = x + 12
    ax_x1 = x + w - 12
    d.line((ax_x0, ax_y1, ax_x1, ax_y1), fill=(170, 170, 170), width=1)
    d.line((ax_x0, ax_y0, ax_x0, ax_y1), fill=(170, 170, 170), width=1)

    # random line chart
    pts = []
    n = 10
    for i in range(n):
        px = ax_x0 + int((ax_x1 - ax_x0) * i / (n - 1))
        val = rng.random()
        py = ax_y1 - int((ax_y1 - ax_y0) * (0.15 + 0.75 * val))
        pts.append((px, py))
    for i in range(len(pts) - 1):
        d.line((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]), fill=(235, 235, 235), width=2)

    # labels
    d.text((ax_x0, ax_y1 + 2), "t", font=f_s, fill=(200, 200, 200))
    d.text((ax_x1 - 20, ax_y0 - 18), "lvl", font=f_s, fill=(200, 200, 200))

    # nonsense stats
    s1 = f"DRIFT {rng.randint(2,19)}%"
    s2 = f"CRC {rng.randint(100000,999999)}"
    s3 = f"NF {rng.randint(18,44)}dB"
    d.text((x + 10, y + h - 52), s1, font=f_s, fill=(220, 220, 220))
    d.text((x + 10, y + h - 34), s2, font=f_s, fill=(220, 220, 220))
    d.text((x + 10, y + h - 16), s3, font=f_s, fill=(220, 220, 220))


def card_screen(w: int, h: int, title: str, lines: List[str], rng: random.Random, brain: str) -> Image.Image:
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    f_title = _font(40)
    f_body = _font(20)

    d.text((56, 72), title, font=f_title, fill=(235, 235, 235))
    y = 142
    for ln in lines[:16]:
        d.text((56, y), ln, font=f_body, fill=(210, 210, 210))
        y += 28

    # infographic panel on cards
    draw_infographic(d, w - 320, 90, 260, 160, rng, f"{brain.upper()} / DIAG")

    return img


def dossier_overlay(img: Image.Image, rng: random.Random, brain: str, anchor: str, title_hint: str):
    """
    Overlays “scraped document” vibe over an image:
    stamps, IDs, redaction bars, annotations.
    """
    d = ImageDraw.Draw(img)
    f = _font(18)
    f2 = _font(14)

    # top stamp
    d.rectangle((18, 18, 360, 64), outline=(220, 220, 220), width=2)
    d.text((28, 28), f"{brain.upper()} / {title_hint}", font=f, fill=(235, 235, 235))

    # case id
    d.text((22, 78), f"ANCHOR: {anchor.upper()}", font=f2, fill=(210, 210, 210))
    d.text((22, 96), f"REF: {rng.randint(1000,9999)}-{rng.randint(10,99)} / FIELD", font=f2, fill=(210, 210, 210))

    # random redaction bars
    for _ in range(6):
        if rng.random() < 0.55:
            x = rng.randint(22, 420)
            y = rng.randint(120, img.height - 60)
            ww = rng.randint(120, 360)
            hh = rng.randint(10, 18)
            d.rectangle((x, y, x + ww, y + hh), fill=(20, 20, 20))

    # margin notes
    if rng.random() < 0.7:
        d.text((img.width - 320, 24), "NOTE:", font=f2, fill=(210, 210, 210))
        d.text((img.width - 320, 44), f"{brain.upper()} PRESENT", font=f2, fill=(210, 210, 210))
        d.text((img.width - 320, 64), "DO NOT PAUSE", font=f2, fill=(210, 210, 210))


def content_frame(w: int, h: int, base: Image.Image, text_lines: List[str], rng: random.Random, brain: str, anchor: str) -> Image.Image:
    img = base.copy()
    img = img.resize((w, h), Image.NEAREST)
    dossier_overlay(img, rng, brain, anchor, "CAPTURE")

    d = ImageDraw.Draw(img)
    f = _font(18)

    # bottom caption bar
    bar_h = 132
    d.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0))
    d.rectangle((0, h - bar_h, w, h - bar_h + 2), fill=(110, 110, 110))

    y = h - bar_h + 14
    for ln in text_lines[:4]:
        d.text((26, y), ln, font=f, fill=(235, 235, 235))
        y += 26

    # small nonsense diagram
    draw_infographic(d, w - 310, h - bar_h + 12, 284, 112, rng, "SIG / TRACE")

    return img


def maybe_jumpscare_frame(img: Image.Image, rng: random.Random) -> Image.Image:
    # harsh flash + contrast; also occasional inverted look
    if rng.random() < 0.35:
        inv = Image.fromarray(255 - np.array(img))
        img = inv
    img = ImageEnhance.Contrast(img).enhance(2.1)
    img = ImageEnhance.Brightness(img).enhance(1.35)
    return img


def render_frames(cfg: dict, meta: dict, bundle: dict, frames_dir: Path):
    w, h = meta["w"], meta["h"]
    fps = meta["fps"]

    style = cfg.get("style", {})
    osd = cfg.get("overlay", {})
    chapters = cfg.get("chapters", [])

    rng = random.Random(meta["theme"]["rng_int"])

    brain = bundle.get("brain", meta["theme"].get("brain", meta["theme"]["keyword"]))
    anchor = bundle.get("anchor", meta["theme"]["anchor"])

    # load images
    bases = []
    for p in bundle.get("images", []):
        try:
            bases.append(Image.open(p).convert("RGB"))
        except Exception:
            pass
    if not bases:
        bases = [make_noise_plate(w, h) for _ in range(6)]

    # text lines from scraped paragraphs (ARG-ified)
    paras = bundle.get("paragraphs", []) or ["The signal persists. The record continues. The room remains present."]
    tech_lines = bundle.get("tech_lines", []) or [f"{brain.upper()} / CRC {rng.randint(100000,999999)}"]

    # Jumpscare schedule
    jumps = cfg.get("jumpscares", {})
    prob = float(jumps.get("probability_per_second", 0.16))
    max_events = int(jumps.get("max_events", 7))
    flash_frames = int(jumps.get("flash_frames", 2))
    hold_frames = int(jumps.get("hold_frames", 7))

    total_frames = int(cfg["video"]["duration_s"] * fps)

    jump_events = []
    for tsec in range(int(cfg["video"]["duration_s"])):
        if len(jump_events) >= max_events:
            break
        if rng.random() < prob:
            jump_events.append(tsec * fps + rng.randint(0, fps - 1))
    jump_set = set()
    for f0 in jump_events:
        for k in range(flash_frames + hold_frames):
            jump_set.add(f0 + k)

    # Timeline
    timeline = []
    cursor = 0
    for ch in chapters:
        n = int(ch["seconds"] * fps)
        timeline.append((cursor, cursor + n, ch["name"]))
        cursor += n
    if cursor < total_frames:
        timeline.append((cursor, total_frames, "ROOM: ATTIC"))

    # room mapping from theme
    room_iter = iter(meta["theme"].get("rooms", []))
    room_cache = {}

    prev_arr = None

    for fi in range(total_frames):
        # which chapter
        ch_name = "CONTENT"
        for a, b, name in timeline:
            if a <= fi < b:
                ch_name = name
                ch_a, ch_b = a, b
                break

        # room label + “different recording”
        room_label = "ROOM FEED"
        room_note = "FIELD"
        if ch_name.startswith("ROOM:"):
            room = ch_name.split("ROOM:", 1)[1].strip()
            if room not in room_cache:
                try:
                    rn = next(room_iter)
                except StopIteration:
                    rn = (room, "field note / partial lock")
                room_cache[room] = rn
            room_label = f"{room_cache[room][0]} / {room_cache[room][1]}"
        elif ch_name == "WARNING":
            room_label = "TAPE LEADER / WARNING"
        elif ch_name == "TECHNICAL NOTES":
            room_label = "TAPE LEADER / TECH"

        # chapter-local progress (for zoom/pan)
        t = 0.0
        if ch_name.startswith("ROOM:"):
            t = (fi - ch_a) / max(1, (ch_b - ch_a - 1))

        # build base frame
        if ch_name == "WARNING":
            tape_id = f"{osd.get('tape_id_prefix','TAPE')}-{(meta['theme']['rng_int']%9999):04d}"
            lines = [
                "THIS RECORDING CONTAINS UNVERIFIED MATERIAL",
                "PLAYBACK MAY INDUCE DISORIENTATION",
                f"TAPE ID: {tape_id}",
                f"SEED: {meta['seed']}",
                f"ORCHESTRATOR: {brain.upper()}",
                "SOURCE: CONSUMER VHS / SP MODE",
                "NOTE: DO NOT PAUSE ON ARTIFACTS",
            ]
            base = card_screen(w, h, "WARNING", lines, rng, brain)

        elif ch_name == "TECHNICAL NOTES":
            lines = [
                f"ANCHOR: {anchor.upper()}",
                f"PRIMARY: {(bundle.get('titles') or ['UNKNOWN'])[0]}",
                "DECODE: FIELD SYNC / RF RECOVERY",
                f"STATUS: {rng.choice(['PARTIAL LOCK','UNSTABLE','SOFT SYNC','DRIFTING'])}",
                f"ROOM COUNT: {len([c for c in chapters if c['name'].startswith('ROOM:')])}",
                "",
            ] + tech_lines[:10]
            base = card_screen(w, h, "TECHNICAL NOTES", lines, rng, brain)

        elif ch_name.startswith("ROOM:"):
            # choose a base image and apply slow zoom/pan
            src = rng.choice(bases)
            # if image is tiny or weird, letterbox after zooming
            zoomed = ken_burns(src, w, h, t, rng)

            # pick creepy “scraped” text
            p = rng.choice(paras)
            words = p.split()
            if len(words) > 18:
                # slice a coherent chunk
                start = rng.randint(0, len(words) - 18)
                chunk = " ".join(words[start:start + 18])
            else:
                chunk = p

            ln1 = redact_line(chunk, rng)
            ln2 = redact_line(rng.choice(paras), rng)
            ln3 = redact_line(rng.choice(tech_lines), rng)
            ln4 = redact_line(f"{brain.upper()} / ROOM INDEX {rng.randint(10,99)} / TAG {rng.randint(100,999)}", rng)

            base = content_frame(w, h, zoomed, [ln1, ln2, ln3, ln4], rng, brain, anchor)

        else:
            base = make_noise_plate(w, h)

        if cfg.get("style", {}).get("black_white", False):
            base = to_grayscale(base)

        d = ImageDraw.Draw(base)
        overlay_vhs_osd(d, w, h, meta, osd, fi, rng, room_label)
        glitch_errors(d, w, h, rng, brain)

        # Jumpscare visuals
        if fi in jump_set:
            base = maybe_jumpscare_frame(base, rng)

        # VHS pass
        base, prev_arr = apply_vhs(base, style, rng, prev_arr)

        (frames_dir / f"frame_{fi:06d}.png").write_bytes(_png_bytes(base))


def _png_bytes(img: Image.Image) -> bytes:
    import io
    bio = io.BytesIO()
    img.save(bio, "PNG")
    return bio.getvalue()

