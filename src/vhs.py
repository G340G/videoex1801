import math
import random
import numpy as np
from PIL import Image


def to_grayscale(img: Image.Image) -> Image.Image:
    return img.convert("L").convert("RGB")


def add_scanlines(arr: np.ndarray, strength: float, rng: random.Random):
    h, w, _ = arr.shape
    line = (np.arange(h) % 2).astype(np.float32)
    line = (1.0 - strength * 0.12) + (line * strength * 0.06)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * line[:, None], 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * line[:, None], 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * line[:, None], 0, 255)


def add_noise(arr: np.ndarray, strength: float, rng: random.Random):
    h, w, _ = arr.shape
    n = rng.random()
    sigma = 6 + strength * 18
    noise = np.random.normal(0, sigma, size=(h, w, 1)).astype(np.float32)
    arr[:] = np.clip(arr.astype(np.float32) + noise, 0, 255)


def jitter(arr: np.ndarray, strength: float, rng: random.Random):
    h, w, _ = arr.shape
    # horizontal jitter by rows
    max_shift = int(2 + strength * 8)
    out = arr.copy()
    for y in range(h):
        if rng.random() < 0.35 * strength:
            s = rng.randint(-max_shift, max_shift)
            out[y] = np.roll(out[y], s, axis=0)
    arr[:] = out


def dropouts(arr: np.ndarray, strength: float, rng: random.Random):
    h, w, _ = arr.shape
    bands = int(1 + strength * 6)
    for _ in range(bands):
        if rng.random() < 0.6 * strength:
            y = rng.randint(0, h - 1)
            bh = rng.randint(2, int(6 + strength * 18))
            y2 = min(h, y + bh)
            # white/black dropout strip
            val = 20 if rng.random() < 0.5 else 235
            arr[y:y2, :, :] = np.clip(arr[y:y2, :, :].astype(np.float32) * 0.25 + val * 0.75, 0, 255).astype(np.uint8)


def chroma_shift(arr: np.ndarray, px: int):
    if px <= 0:
        return
    # simulate chroma misalignment by shifting channels
    arr[:, :, 0] = np.roll(arr[:, :, 0], px, axis=1)
    arr[:, :, 2] = np.roll(arr[:, :, 2], -px, axis=1)


def flicker(arr: np.ndarray, amount: float, rng: random.Random):
    # global brightness flicker
    f = 1.0 + (rng.random() * 2 - 1) * amount * 0.12
    arr[:] = np.clip(arr.astype(np.float32) * f, 0, 255).astype(np.uint8)


def pframe_smear(cur: np.ndarray, prev: np.ndarray, strength: float, rng: random.Random):
    """
    Temporal block smear to evoke inter-frame compression artifacts.
    """
    if prev is None or strength <= 0:
        return cur
    h, w, _ = cur.shape
    out = cur.copy()
    bs = int(8 + strength * 24)
    blocks = int(10 + strength * 60)
    for _ in range(blocks):
        x = rng.randint(0, max(0, w - bs))
        y = rng.randint(0, max(0, h - bs))
        x2, y2 = x + bs, y + bs
        # blend previous block into current with random alpha
        a = 0.25 + rng.random() * (0.55 * strength)
        out[y:y2, x:x2] = np.clip(
            out[y:y2, x:x2].astype(np.float32) * (1 - a) + prev[y:y2, x:x2].astype(np.float32) * a,
            0, 255
        ).astype(np.uint8)
    return out


def apply_vhs(img: Image.Image, cfg_style: dict, rng: random.Random, prev_arr: np.ndarray | None):
    arr = np.array(img).astype(np.uint8)

    if cfg_style.get("scanlines", 1):
        add_scanlines(arr, cfg_style.get("vhs_strength", 0.8), rng)

    add_noise(arr, cfg_style.get("vhs_strength", 0.8), rng)
    jitter(arr, cfg_style.get("jitter_strength", 0.6), rng)
    dropouts(arr, cfg_style.get("dropout_strength", 0.5), rng)
    chroma_shift(arr, int(cfg_style.get("chroma_shift", 1)))
    flicker(arr, cfg_style.get("film_flicker", 0.35), rng)

    arr = pframe_smear(arr, prev_arr, cfg_style.get("pframe_smear", 0.4), rng)
    return Image.fromarray(arr), arr
