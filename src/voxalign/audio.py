"""Shared audio + text helpers: decoding, framing, RMS, tokenisation."""
from __future__ import annotations
import os
import re
import subprocess
import numpy as np

SR = 16000          # working sample rate
FRAME = 320         # 20 ms at 16 kHz


def norm_tokens(text: str) -> list[str]:
    """Lowercase, strip punctuation, split to word tokens."""
    return [t for t in re.sub(r"[^a-z0-9\s]", " ", text.lower()).split() if t]


def decode(path: str, sr: int = SR) -> np.ndarray:
    """Decode any ffmpeg-readable file to a mono float32 array in [-1, 1]."""
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
           "-f", "s16le", "-"]
    raw = subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def frame_rms(x: np.ndarray, n_frames: int, frame: int = FRAME) -> np.ndarray:
    """Per-frame RMS energy over non-overlapping frames."""
    x = x[: n_frames * frame].reshape(n_frames, frame)
    return np.sqrt(np.mean(x * x, axis=1) + 1e-12)


def ffmpeg_available() -> bool:
    from shutil import which
    return which("ffmpeg") is not None
