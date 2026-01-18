import math
import random
import wave
from typing import Dict

import numpy as np


def _tone(freq, t):
    return np.sin(2 * math.pi * freq * t)


def _env(t, a=0.01, d=0.2, s=0.6, r=0.2, dur=1.0):
    # simple ADSR envelope
    out = np.zeros_like(t)
    attack = a
    decay = d
    release = r
    sustain_level = s
    sustain_time = max(0.0, dur - (attack + decay + release))
    # segments
    for i, ti in enumerate(t):
        if ti < attack:
            out[i] = (ti / max(1e-6, attack))
        elif ti < attack + decay:
            x = (ti - attack) / max(1e-6, decay)
            out[i] = 1.0 + (sustain_level - 1.0) * x
        elif ti < attack + decay + sustain_time:
            out[i] = sustain_level
        elif ti < dur:
            x = (ti - (attack + decay + sustain_time)) / max(1e-6, release)
            out[i] = sustain_level * (1.0 - x)
        else:
            out[i] = 0.0
    return out


def _noise(n):
    return np.random.uniform(-1, 1, size=n)


def _clip(x):
    return np.clip(x, -1.0, 1.0)


def _write_wav(path, sr, audio_float):
    audio = (audio_float * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())


def render_audio_wav(cfg: dict, meta: dict, bundle: dict, out_wav: str):
    sr = 48000
    dur = float(cfg["video"]["duration_s"])
    n = int(sr * dur)
    t = np.arange(n, dtype=np.float32) / sr

    rng = random.Random(meta["theme"]["rng_int"])

    # Base: tape hiss + low rumble
    hiss = _noise(n) * 0.06
    rumble = _tone(36 + rng.randint(-3, 3), t) * 0.10
    rumble += _tone(72 + rng.randint(-6, 6), t) * 0.05

    # Creepy “unstable” drones
    lfo = (0.5 + 0.5 * np.sin(2 * math.pi * (0.08 + rng.random() * 0.05) * t)).astype(np.float32)
    drone_f = 110 + rng.randint(-20, 20)
    drone = _tone(drone_f, t) * (0.08 + 0.08 * lfo)
    drone += _tone(drone_f * 0.5, t) * (0.06 + 0.06 * (1 - lfo))

    # Sparse “PSA-ish” melodic fragments but warped (very low in mix)
    notes = [220, 247, 196, 165, 196, 220]
    frag = np.zeros(n, dtype=np.float32)
    step = int(sr * 0.9)
    for i, f in enumerate(notes):
        start = i * step
        if start >= n:
            break
        length = min(step, n - start)
        tt = np.arange(length, dtype=np.float32) / sr
        det = (rng.random() * 2 - 1) * 3.0
        wave1 = _tone(f + det, tt) * 0.06
        wave2 = _tone((f * 2) + det, tt) * 0.02
        env = _env(tt, dur=tt[-1] if len(tt) > 1 else 0.1)
        frag[start:start + length] += (wave1 + wave2) * env
    # tape wobble on fragment
    frag *= (0.7 + 0.3 * np.sin(2 * math.pi * 0.3 * t))

    # Jumpscare stingers: abrupt noise + sine spike
    jumps = cfg.get("jumpscares", {})
    prob = float(jumps.get("probability_per_second", 0.12))
    max_events = int(jumps.get("max_events", 6))
    events = []
    for s in range(int(dur)):
        if len(events) >= max_events:
            break
        if rng.random() < prob:
            events.append(s + rng.random())

    sting = np.zeros(n, dtype=np.float32)
    for et in events:
        start = int(et * sr)
        length = int(sr * (0.18 + rng.random() * 0.22))
        end = min(n, start + length)
        if end <= start:
            continue
        tt = np.arange(end - start, dtype=np.float32) / sr
        burst = _noise(end - start) * 0.9
        spike_f = rng.choice([700, 900, 1200, 1500, 2400, 3200])
        spike = _tone(spike_f, tt) * 0.6
        env = np.exp(-tt * (10 + rng.random() * 20)).astype(np.float32)
        sting[start:end] += (burst + spike) * env

    # Final mix with gentle tape saturation
    audio = hiss + rumble + drone + (frag * 0.6) + sting * 0.8
    audio = np.tanh(audio * 1.6)  # saturation / tape compression
    audio *= 0.9

    _write_wav(out_wav, sr, _clip(audio))
