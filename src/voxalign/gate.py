"""Stage 1: dominant-energy gating.

Each mic bleeds the whole room, so "per-channel = ground truth" fails: every
channel transcribes everyone. For each short frame the true speaker is the
LOUDEST mic. Keep each channel only on frames where it is dominant; silence the
rest. Feeding the gated channels to any ASR yields clean per-speaker text.
"""
from __future__ import annotations
import os
import numpy as np
from scipy.io import wavfile
from .audio import SR, FRAME, decode, frame_rms


def _median_labels(labels: np.ndarray, w: int) -> np.ndarray:
    if w < 3:
        return labels
    h = w // 2
    pad = np.pad(labels, (h, h), mode="edge")
    out = labels.copy()
    for i in range(len(labels)):
        out[i] = np.bincount(pad[i:i + w] + 1).argmax() - 1  # -1 = silence
    return out


def gate(
    files: list[str],
    names: list[str],
    out_dir: str,
    margin: float = 1.25,
    smooth: int = 9,
    floor_pctl: float = 45.0,
) -> dict[str, float]:
    """Write <out_dir>/<name>.wav for each channel, gated to its dominant frames.

    Returns a dict of name -> kept minutes (plus 'silence').
    """
    assert len(files) == len(names), "files/names length mismatch"
    os.makedirs(out_dir, exist_ok=True)

    sigs = [decode(f) for f in files]
    n = min(len(s) for s in sigs)
    sigs = [s[:n] for s in sigs]
    nf = n // FRAME

    rms = np.stack([frame_rms(s, nf) for s in sigs], axis=0)   # (C, nf)
    room = rms.max(axis=0)
    floor = np.percentile(room, floor_pctl)

    order = np.argsort(rms, axis=0)
    top = order[-1]
    top_val = np.take_along_axis(rms, top[None], axis=0)[0]
    run_val = np.take_along_axis(rms, order[-2][None], axis=0)[0]

    labels = top.copy()
    labels[room < floor] = -1
    labels[top_val < margin * run_val] = -1
    labels = _median_labels(labels, smooth)

    stats: dict[str, float] = {}
    for ci, name in enumerate(names):
        mask_frames = labels == ci
        mask = np.repeat(mask_frames, FRAME)
        g = sigs[ci][: len(mask)].copy()
        g[~mask] = 0.0
        out = (np.clip(g, -1, 1) * 32767).astype(np.int16)
        wavfile.write(os.path.join(out_dir, name + ".wav"), SR, out)
        stats[name] = float(mask_frames.sum()) * FRAME / SR / 60.0
    stats["silence"] = float((labels == -1).sum()) * FRAME / SR / 60.0
    return stats
