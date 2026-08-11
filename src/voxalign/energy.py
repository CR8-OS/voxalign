"""Stage 4: energy tiebreak for leftover crosstalk blocks.

Blocks that gating blanked (overlap / quiet interjections) never reach the ASR,
so text can't place them. Instead: locate the block on the RAW recording
timeline using the ungated (bleed) transcripts (every mic caught the words),
then read per-channel RMS in that window and take the loudest mic. If no mic
clearly wins, leave it unattributed (true simultaneous overlap).
"""
from __future__ import annotations
import os
import numpy as np
from difflib import SequenceMatcher
from .audio import SR, FRAME, decode, frame_rms, norm_tokens


def _chan_streams(bleed: list[dict], names: list[str]) -> dict:
    streams = {n: {"tok": [], "t": []} for n in names}
    for seg in bleed:
        s = seg["spk"]
        if s not in streams:
            continue
        toks = norm_tokens(seg["text"])
        if not toks:
            continue
        a, b = seg["start"], seg["end"]
        for i, tk in enumerate(toks):
            streams[s]["tok"].append(tk)
            streams[s]["t"].append(a + (i + 0.5) / len(toks) * (b - a))
    return streams


def energy_tiebreak(
    blocks: list[dict],
    bleed: list[dict],
    files: list[str],
    names: list[str],
    margin: float = 1.20,
    pad: float = 0.10,
    min_run: int = 3,
) -> list[dict]:
    """Resolve unattributed blocks in place. Returns a per-block report list."""
    streams = _chan_streams(bleed, names)
    sigs = {n: decode(f) for n, f in zip(names, files)}
    N = min(len(s) for s in sigs.values())
    nf = N // FRAME
    rms = {n: frame_rms(sigs[n][:N], nf) for n in names}

    report = []
    for b in blocks:
        if b["spk"]:
            continue
        bt = norm_tokens(b["text"])
        best = None
        for n in names:
            ct = streams[n]["tok"]
            if not ct or not bt:
                continue
            m = SequenceMatcher(None, ct, bt, autojunk=False).find_longest_match(
                0, len(ct), 0, len(bt))
            if m.size >= min_run and (best is None or m.size > best[0]):
                t0 = streams[n]["t"][m.a]
                t1 = streams[n]["t"][m.a + m.size - 1]
                best = (m.size, n, t0, t1)
        if best is None:
            report.append({"tc": b["start"], "result": "S?", "reason": "no-raw-match",
                           "text": b["text"]})
            continue
        _, _loc, t0, t1 = best
        f0 = max(0, int((min(t0, t1) - pad) * SR / FRAME))
        f1 = min(nf, int((max(t0, t1) + pad) * SR / FRAME) + 1)
        energies = {n: float(np.mean(rms[n][f0:f1])) for n in names}
        rank = sorted(energies, key=lambda k: -energies[k])
        top, second = rank[0], rank[1]
        ratio = energies[top] / (energies[second] + 1e-9)
        if ratio >= margin:
            b["spk"] = top
            b["energy"] = True
            report.append({"tc": b["start"], "result": top, "ratio": round(ratio, 2),
                           "vs": second, "text": b["text"]})
        else:
            report.append({"tc": b["start"], "result": "S?", "reason": "overlap",
                           "top": top, "text": b["text"]})
    return report
