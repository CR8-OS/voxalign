"""Stage 3: reconcile per-channel transcripts onto the edited caption file.

Each edited caption block is matched independently across the whole per-channel
(ground-truth) stream, so reordering (a cold open) and small edits are handled.
Blocks with no confident match are left unattributed for the energy stage / a
human pass. A block whose confident neighbours agree is filled by context.
"""
from __future__ import annotations
import json
import re
from difflib import SequenceMatcher
from .audio import norm_tokens

# SMPTE "HH:MM:SS:FF - HH:MM:SS:FF" or standard SRT "HH:MM:SS,mmm --> HH:MM:SS,mmm"
_TC = re.compile(
    r"^(\d\d:\d\d:\d\d[:;,]\d{2,3})\s*(?:-|-->)\s*(\d\d:\d\d:\d\d[:;,]\d{2,3})"
)


def parse_edited(path: str) -> list[dict]:
    """Parse an edited caption file (SMPTE or SRT) into timecoded text blocks."""
    blocks, cur = [], None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = _TC.match(line)
        if m:
            if cur:
                blocks.append(cur)
            cur = {"start": m.group(1), "end": m.group(2), "text": ""}
        elif cur is not None and line.strip() and not line.strip().isdigit():
            cur["text"] = (cur["text"] + " " + line.strip()).strip()
    if cur:
        blocks.append(cur)
    return blocks


def build_raw_stream(raw: list[dict]) -> tuple[list[str], list[str]]:
    toks, spk = [], []
    for seg in raw:
        for t in norm_tokens(seg["text"]):
            toks.append(t)
            spk.append(seg["spk"])
    return toks, spk


def _attribute(block_tokens, raw_toks, raw_spk, min_run=3):
    if not block_tokens:
        return None, 0
    sm = SequenceMatcher(None, raw_toks, block_tokens, autojunk=False)
    m = sm.find_longest_match(0, len(raw_toks), 0, len(block_tokens))
    if m.size < min(min_run, len(block_tokens)):
        return None, m.size
    region = raw_spk[m.a: m.a + m.size]
    counts: dict[str, int] = {}
    for s in region:
        counts[s] = counts.get(s, 0) + 1
    return max(counts, key=counts.get), m.size


def reconcile(raw: list[dict], blocks: list[dict], min_run: int = 3) -> dict:
    """Attribute a speaker to each block; fill gaps where neighbours agree.

    Mutates blocks in place (adds 'spk' and 'inferred'). Returns stat counts.
    """
    raw_toks, raw_spk = build_raw_stream(raw)
    matched = 0
    for b in blocks:
        spk, _ = _attribute(norm_tokens(b["text"]), raw_toks, raw_spk, min_run)
        b["spk"] = spk
        b["inferred"] = False
        if spk:
            matched += 1

    def nearest(idx, step):
        j = idx + step
        while 0 <= j < len(blocks):
            if blocks[j]["spk"] and not blocks[j]["inferred"]:
                return blocks[j]["spk"]
            j += step
        return None

    filled = 0
    for i, b in enumerate(blocks):
        if b["spk"]:
            continue
        prev, nxt = nearest(i, -1), nearest(i, 1)
        if prev and prev == nxt:
            b["spk"] = prev
            b["inferred"] = True
            filled += 1

    remaining = sum(1 for b in blocks if not b["spk"])
    return {"matched": matched, "filled": filled, "remaining": remaining}


def write_transcript(blocks: list[dict], path: str, unknown: str = "S?") -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for b in blocks:
            tag = ""
            if b.get("energy"):
                tag = " [energy]"
            elif b.get("inferred"):
                tag = " [inferred]"
            elif b.get("confirmed"):
                tag = " [confirmed]"
            fh.write(f"{b['start']} - {b['end']}\n{(b['spk'] or unknown)}: "
                     f"{b['text']}{tag}\n\n")


def load_raw(path: str) -> list[dict]:
    return json.load(open(path, encoding="utf-8"))
