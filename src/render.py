import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from .vhs import apply_vhs, to_grayscale


def _font(size: int):
    # Pillow default bitmap font is too small; try common fonts, fall back to default.
    for name in ["DejaVuSansMono.ttf", "DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_noise_plate(w: int, h: int, rng: random.Random) -> Image.Image:
    arr = np.random.randint(0, 255, size=(h, w), dtype=np.uint8)
    img = Image.fromarray(arr, mode="L").convert("RGB")
    return img


def letterbox(img: Image.Image, w: int, h: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((w, h))
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    x = (w - img.width) // 2
    y = (h - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def overlay_vhs_osd(draw: ImageDraw.ImageDraw, w: int, h: int, meta: dict, osd: dict, frame_idx: int, rng: random.Random):
    # top-left REC
    f_small = _font(18)
    f_med = _font(22)
    f_big = _font(28)

    # “REC” and dot
    draw.text((28, 20), "REC", font=f_big, fill=(235, 235, 235))
    draw.ellipse((10, 26, 22, 38), fill=(235, 235, 235))

    # timecode
    fps = meta["fps"]
    total_frames = int(meta["duration_s"] * fps)
    seconds = frame_idx / fps
    hh = int(seconds // 3600)
    mm = int((seconds % 3600) // 60)
    ss = int(seconds % 60)
    ff = int(frame_idx % fps)
    tc = f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"
    draw.text((w - 220, 22), tc, font=f_med, fill=(235, 235, 235))

    # date + location
    # fake date derived from seed (stable-ish)
    seed_int = meta["theme"]["rng_int"]
    day = 1 + (seed_int % 28)
    month = 1 + ((seed_int // 31) % 12)
    year = 1991 + ((seed_int // 97) % 9)
    date = f"{day:02d}.{month:02d}.{year:04d}"
    loc = rng.choice(osd.get("location_pool", ["UNKNOWN"]))
    draw.text((28, h - 54), f"{date}  {loc}", font=f_small, fill=(235, 235, 235))

    # tracking / SP
    track = 20 + int(40 * (0.5 + 0.5 * math.sin(frame_idx * 0.03)))
    draw.text((w - 310, h - 54), f"TRK {track:02d}  SP", font=f_small, fill=(235, 235, 235))

    # subtle border lines
    draw.rectangle((6, 6, w - 6, h - 6), outline=(90, 90, 90), width=2)


def glitch_errors(draw: ImageDraw.ImageDraw, w: int, h: int, rng: random.Random):
    if rng.random() < 0.22:
        f = _font(20)
        msgs = [
            "ERROR: DROP FRAME",
            "SYNC LOST",
            "HEAD CLOG DETECTED",
            "RF INTERFERENCE",
            "TRACKING MISALIGN",
            "CARRIER DRIFT",
            "FIELD ORDER SWAP",
        ]
        msg = rng.choice(msgs)
        x = rng.randint(40, w - 340)
        y = rng.randint(80, h - 120)
        draw.text((x, y), msg, font=f, fill=(235, 235, 235))


def card_screen(w: int, h: int, title: str, lines: List[str], rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    f_title = _font(44)
    f_body = _font(22)

    d.text((60, 90), title, font=f_title, fill=(235, 235, 235))
    y = 170
    for ln in lines[:14]:
        d.text((60, y), ln, font=f_body, fill=(210, 210, 210))
        y += 30

    # fake “VHS text noise”
    for _ in range(20):
        if rng.random() < 0.35:
            x = rng.randint(30, w - 30)
            y = rng.randint(20, h - 20)
            d.line((x, y, x + rng.randint(20, 120), y), fill=(120, 120, 120), width=1)

    return img


def content_frame(w: int, h: int, base: Image.Image, text_lines: List[str], rng: random.Random) -> Image.Image:
    img = letterbox(base, w, h)
    d = ImageDraw.Draw(img)
    f = _font(22)

    # bottom caption bar
    bar_h = 140
    d.rectangle((0, h - bar_h, w, h), fill=(0, 0, 0))
    d.rectangle((0, h - bar_h, w, h - bar_h + 2), fill=(110, 110, 110))

    # typed-looking text (seeded selection)
    y = h - bar_h + 18
    for ln in text_lines[:4]:
        d.text((38, y), ln, font=f, fill=(235, 235, 235))
        y += 28

    return img


def maybe_jumpscare_frame(w: int, h: int, img: Image.Image, rng: random.Random) -> Image.Image:
    # abrupt “flash” look
    enh = ImageEnhance.Contrast(img)
    img = enh.enhance(1.8)
    enhb = ImageEnhance.Brightness(img)
    img = enhb.enhance(1.3)
    return img


def render_frames(cfg: dict, meta: dict, bundle: dict, frames_dir: Path):
    w, h = meta["w"], meta["h"]
    fps = meta["fps"]

    style = cfg.get("style", {})
    osd = cfg.get("overlay", {})
    chapters = cfg.get("chapters", [])

    rng = random.Random(meta["theme"]["rng_int"])

    # Prepare images (or fallback noise plates)
    bases = []
    for p in bundle.get("images", []):
        try:
            im = Image.open(p).convert("RGB")
            bases.append(im)
        except Exception:
            pass
    if not bases:
        bases = [make_noise_plate(w, h, rng) for _ in range(4)]

    # Prepare text chunks
    paras = bundle.get("paragraphs", []) or ["The signal persists. The record continues. The room remains present."]
    tech_lines = bundle.get("tech_lines", [])

    # Jumpscare schedule
    jumps = cfg.get("jumpscares", {})
    prob = float(jumps.get("probability_per_second", 0.12))
    max_events = int(jumps.get("max_events", 6))
    flash_frames = int(jumps.get("flash_frames", 2))
    hold_frames = int(jumps.get("hold_frames", 6))

    total_frames = int(cfg["video"]["duration_s"] * fps)
    jump_events = []
    for t in range(int(cfg["video"]["duration_s"])):
        if len(jump_events) >= max_events:
            break
        if rng.random() < prob:
            # place within second
            frame = t * fps + rng.randint(0, fps - 1)
            jump_events.append(frame)
    jump_set = set()
    for f0 in jump_events:
        for k in range(flash_frames + hold_frames):
            jump_set.add(f0 + k)

    # Build chapter timeline
    timeline = []
    cursor = 0
    for ch in chapters:
        n = int(ch["seconds"] * fps)
        timeline.append((cursor, cursor + n, ch["name"]))
        cursor += n
    # Safety: if timeline shorter, extend last segment
    if cursor < total_frames:
        timeline.append((cursor, total_frames, "CHAPTER 4: RESIDUAL"))

    prev_arr = None

    for fi in range(total_frames):
        # Which chapter?
        ch_name = "CONTENT"
        for a, b, name in timeline:
            if a <= fi < b:
                ch_name = name
                break

        # Chapter cards
        if ch_name == "WARNING":
            lines = [
                "THIS RECORDING CONTAINS UNVERIFIED MATERIAL",
                "PLAYBACK MAY INDUCE DISORIENTATION",
                f"TAPE ID: {cfg['overlay'].get('tape_id_prefix','TAPE')}-{(meta['theme']['rng_int']%9999):04d}",
                f"SEED: {meta['seed']}",
                "SOURCE: CONSUMER VHS / SP MODE",
                "NOTE: DO NOT PAUSE ON ARTIFACTS",
            ]
            base = card_screen(w, h, "WARNING", lines, rng)

        elif ch_name == "TECHNICAL NOTES":
            lines = [
                f"ANCHOR: {meta['theme']['anchor'].upper()}",
                f"PRIMARY: {bundle.get('titles', ['UNKNOWN'])[0]}",
                "DECODE: FIELD SYNC / RF RECOVERY",
                "STATUS: PARTIAL LOCK",
                "",
            ] + tech_lines[:10]
            base = card_screen(w, h, "TECHNICAL NOTES", lines, rng)

        elif "CHAPTER" in ch_name:
            lines = [
                f"ANCHOR: {meta['theme']['anchor'].upper()}",
                f"MODULE: {ch_name}",
                f"DRIFT: {rng.randint(2, 19)}%",
                f"DROP RATE: {rng.randint(1, 13)}%",
                f"CRC: {rng.randint(100000,999999)}",
                "FIELD: INTERLACED",
                "AUDIO: LINEAR",
                "NOTES: LOCALIZED NOISE PRESENT",
            ]
            base = card_screen(w, h, ch_name, lines, rng)

        else:
            base = rng.choice(bases)
            # text lines: slice from paragraphs + mutate a little
            p = rng.choice(paras)
            words = p.split(" ")
            rng.shuffle(words)
            ln1 = " ".join(words[: min(10, len(words))])
            ln2 = p[: min(120, len(p))]
            ln3 = f"ANCHOR {meta['theme']['keyword'].upper()} / INDEX {rng.randint(10,99)}"
            ln4 = rng.choice(tech_lines) if tech_lines else "SYNC ACTIVE / NOISE FLOOR RISING"
            base = content_frame(w, h, base, [ln1, ln2, ln3, ln4], rng)

        if cfg.get("style", {}).get("black_white", False):
            base = to_grayscale(base)

        # Add OSD & errors before VHS pass
        d = ImageDraw.Draw(base)
        overlay_vhs_osd(d, w, h, meta, osd, fi, rng)
        glitch_errors(d, w, h, rng)

        # Jumpscare (visual)
        if fi in jump_set:
            base = maybe_jumpscare_frame(w, h, base, rng)

        # VHS pass (noise/jitter/dropouts/chroma/pframe smear)
        base, prev_arr = apply_vhs(base, style, rng, prev_arr)

        outp = frames_dir / f"frame_{fi:06d}.png"
        base.save(outp, "PNG")
