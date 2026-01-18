## 4) `generate.py`

```python
#!/usr/bin/env python3
import argparse
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from src.theme import make_seed_and_theme
from src.scrape import scrape_bundle
from src.render import render_frames
from src.audio import render_audio_wav
from src.ffmpeg_utils import encode_video_from_frames, mux_audio_video


def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    out_path = args.out or cfg.get("out", "out.mp4")

    w = int(cfg["video"]["width"])
    h = int(cfg["video"]["height"])
    fps = int(cfg["video"]["fps"])
    duration_s = float(cfg["video"]["duration_s"])

    seed, theme = make_seed_and_theme(cfg.get("seed", "AUTO"))
    print(f"[seed] {seed}")
    print(f"[theme] {theme['keyword']} | {theme['topic']}")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        frames_dir = td / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        # 1) scrape text + images based on theme
        bundle = scrape_bundle(cfg, theme, td)

        # 2) render frames
        meta = {
            "seed": seed,
            "theme": theme,
            "fps": fps,
            "w": w,
            "h": h,
            "duration_s": duration_s,
        }
        render_frames(cfg, meta, bundle, frames_dir)

        # 3) generate audio
        wav_path = td / "audio.wav"
        render_audio_wav(cfg, meta, bundle, str(wav_path))

        # 4) encode silent video then mux audio
        silent_mp4 = td / "silent.mp4"
        encode_video_from_frames(
            frames_glob=str(frames_dir / "frame_%06d.png"),
            fps=fps,
            width=w,
            height=h,
            out_mp4=str(silent_mp4),
        )
        mux_audio_video(str(silent_mp4), str(wav_path), out_path)

    # Ensure output exists
    if not Path(out_path).exists():
        raise SystemExit("Failed to create output video.")
    print(f"[ok] wrote {out_path}")


if __name__ == "__main__":
    main()
