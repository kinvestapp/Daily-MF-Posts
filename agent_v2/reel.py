"""Build a 9:16 Reel (mp4) from the three carousel slides + a royalty-free audio track.

Slow zoom on each slide, soft cross-fades, audio faded in/out. Needs ffmpeg.
Audio comes from assets/audio/*.m4a|mp3 (original tracks shipped; drop in licensed ones any time).
"""
import glob
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "assets" / "audio"
SLIDE_SECONDS = [4.5, 4.5, 5.0]
FADE = 0.5
FPS = 30


def pick_track(rng=None):
    tracks = sorted(glob.glob(str(AUDIO_DIR / "*.m4a")) + glob.glob(str(AUDIO_DIR / "*.mp3")))
    if not tracks:
        return None
    return (rng or random).choice(tracks)


def build_reel(slide_paths, out_path, track=None):
    """Returns (out_path, track_used)."""
    track = track or pick_track()
    n = len(slide_paths)
    durs = SLIDE_SECONDS[:n]
    total = sum(durs) - FADE * (n - 1)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p, d in zip(slide_paths, durs):
        cmd += ["-loop", "1", "-t", f"{d + FADE}", "-i", str(p)]
    if track:
        cmd += ["-stream_loop", "-1", "-i", str(track)]
    f = []
    for i, d in enumerate(durs):
        frames = int((d + FADE) * FPS)
        # blurred copy of the slide fills the 9:16 canvas; the sharp slide zooms slowly on top
        f.append(
            f"[{i}:v]split[a{i}][b{i}];"
            f"[a{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=60:6,eq=brightness=0.03,format=yuv420p[bg{i}];"
            f"[b{i}]scale=1440:1800,zoompan=z='min(1.0+0.0007*on,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s=1080x1350:fps={FPS},format=yuv420p[fg{i}];"
            f"[bg{i}][fg{i}]overlay=0:(H-h)/2-60,setsar=1[v{i}]"
        )
    last, offset = "v0", 0.0
    for i in range(1, n):
        offset += durs[i - 1] - FADE
        f.append(f"[{last}][v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.2f}[x{i}]")
        last = f"x{i}"
    maps = ["-map", f"[{last}]"]
    if track:
        f.append(f"[{n}:a]atrim=0:{total:.2f},afade=t=in:d=0.5,afade=t=out:st={total - 1.5:.2f}:d=1.5[a]")
        maps += ["-map", "[a]"]
    cmd += ["-filter_complex", ";".join(f)] + maps
    cmd += ["-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if track:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd.append(str(out_path))
    subprocess.run(cmd, check=True)
    return str(out_path), (Path(track).name if track else None)
