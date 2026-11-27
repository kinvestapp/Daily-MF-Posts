"""Generate original, royalty-free background tracks (soft lo-fi pad + pluck + light beat).

These are synthesized from scratch, so there is no licensing issue. To use other licensed
tracks instead, drop .m4a/.mp3 files into assets/audio/ - the Reel builder picks one at random.
Run: python tools/make_audio.py
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"

def note(freq, dur, kind="pluck"):
    t = np.arange(int(SR * dur)) / SR
    if kind == "pad":
        w = sum(np.sin(2 * np.pi * freq * (1 + d) * t) for d in (-0.003, 0, 0.003)) / 3
        env = np.minimum(t / 0.6, 1) * np.minimum((dur - t) / 0.8, 1)
        return 0.16 * w * np.clip(env, 0, 1)
    w = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t) + 0.15 * np.sin(2 * np.pi * 3 * freq * t)
    return 0.22 * w * np.exp(-t * 5.5) * np.minimum(t / 0.005, 1)

def kick(dur=0.35):
    t = np.arange(int(SR * dur)) / SR
    return 0.5 * np.sin(2 * np.pi * (55 + 90 * np.exp(-t * 28)) * t) * np.exp(-t * 11)

def hat(dur=0.06, rng=np.random.default_rng(3)):
    t = np.arange(int(SR * dur)) / SR
    return 0.07 * rng.standard_normal(len(t)) * np.exp(-t * 70)

def mix(buf, sig, start):
    i = int(start * SR)
    buf[i:i + len(sig)] += sig[: max(0, len(buf) - i)]

def freq(m):  # midi -> Hz
    return 440 * 2 ** ((m - 69) / 12)

TRACKS = {
    # name: (bpm, chords as (root midi, third interval))
    "calm-growth": (84, [(57, 3), (53, 4), (48, 4), (55, 4)]),       # Am F C G
    "bright-start": (96, [(48, 4), (55, 4), (57, 3), (53, 4)]),      # C G Am F
    "steady-habit": (78, [(50, 3), (46, 4), (53, 4), (48, 4)]),      # Dm Bb F C
}

def render(name, bpm, chords, bars=8):
    beat = 60 / bpm
    bar = 4 * beat
    total = bars * bar
    buf = np.zeros(int(SR * (total + 1.5)))
    for b in range(bars):
        root, third = chords[b % len(chords)]
        start = b * bar
        for m in (root - 12, root, root + third, root + 7):
            mix(buf, note(freq(m), bar + 0.4, "pad"), start)
        arp = [root + 12, root + third + 12, root + 19, root + third + 12]
        for k in range(8):
            mix(buf, note(freq(arp[k % 4]), 0.5), start + k * beat / 2)
        for k in (0, 2):
            mix(buf, kick(), start + k * beat)
        for k in range(8):
            mix(buf, hat(), start + k * beat / 2 + beat / 4)
    buf = np.tanh(buf * 1.1)
    buf /= np.max(np.abs(buf)) / 0.85
    wav = OUT / f"{name}.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((buf * 32767).astype(np.int16).tobytes())
    out = OUT / f"{name}.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "128k", str(out)], check=True)
    wav.unlink()
    print(out, f"{total:.1f}s")

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, (bpm, ch) in TRACKS.items():
        render(n, bpm, ch)
