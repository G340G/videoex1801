import subprocess


def _run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{p.stdout}")


def encode_video_from_frames(frames_glob: str, fps: int, width: int, height: int, out_mp4: str):
    # frames_glob: /path/frame_%06d.png
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", frames_glob,
        "-vf", f"scale={width}:{height}:flags=neighbor",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "18",
        out_mp4
    ]
    _run(cmd)


def mux_audio_video(video_mp4: str, audio_wav: str, out_mp4: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", video_mp4,
        "-i", audio_wav,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_mp4
    ]
    _run(cmd)
