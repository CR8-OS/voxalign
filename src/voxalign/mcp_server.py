"""VoxAlign MCP server.

Exposes the VoxAlign pipeline as MCP tools so any MCP client (Claude Code,
Cowork, IBM Bob, etc.) can turn per-channel mics + an edited SRT into a
speaker-attributed transcript. Imports the package directly, no subprocess.

Run:  voxalign-mcp            (stdio)
   or python -m voxalign.mcp_server
Install the extra:  pip install "voxalign[mcp]"   (add [whisper] for transcribe)
"""
from __future__ import annotations
import os

from mcp.server import MCPServer

from . import __version__
from .reconcile import (parse_edited, reconcile as _reconcile, write_transcript,
                        load_raw, parse_attributed)

server = MCPServer("voxalign", version=__version__)


def _need(*paths: str) -> None:
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            "Input file(s) not found: " + ", ".join(missing) +
            ". Pass absolute paths that exist on the machine running this server.")


@server.tool()
def voxalign_reconcile(raw_json_path: str, edited_srt_path: str, out_path: str,
                       min_run: int = 3) -> dict:
    """Attribute a speaker to every block of an edited SRT by matching it against
    per-channel (ground-truth) transcripts. Handles cold-open reordering and fills
    gaps where both confident neighbours agree. Writes the attributed transcript to
    out_path. raw_json_path is a JSON list of {start,end,spk,text} per channel.
    Returns counts: matched, filled, remaining (blocks left as S?)."""
    _need(raw_json_path, edited_srt_path)
    raw = load_raw(raw_json_path)
    blocks = parse_edited(edited_srt_path)
    stats = _reconcile(raw, blocks, min_run=min_run)
    write_transcript(blocks, out_path)
    return {"blocks": len(blocks), **stats, "out_path": out_path}


@server.tool()
def voxalign_gate(files: list[str], names: list[str], out_dir: str,
                  margin: float = 1.25) -> dict:
    """Dominant-energy gating. Keep each channel only on the frames where that mic
    is loudest, silencing the rest, which removes room bleed before transcription.
    files and names are parallel lists (one name per mic). Writes <out_dir>/<name>.wav.
    Returns voiced minutes kept per channel plus silence. Requires ffmpeg."""
    if len(files) != len(names):
        raise ValueError("files and names must be the same length (one name per mic).")
    _need(*files)
    from .gate import gate as _gate
    stats = _gate(files, names, out_dir, margin=margin)
    return {"minutes_per_channel": stats, "out_dir": out_dir}


@server.tool()
def voxalign_transcribe(files: list[str], names: list[str], out_json: str,
                        model: str = "base.en", device: str | None = None) -> dict:
    """Transcribe each channel with faster-whisper and tag every segment with that
    channel's speaker name. Writes a JSON list of {start,end,spk,text} to out_json,
    ready for voxalign_reconcile. Requires the [whisper] extra and ffmpeg. device is
    'cuda', 'cpu', or omit to auto-detect."""
    if len(files) != len(names):
        raise ValueError("files and names must be the same length (one name per mic).")
    _need(*files)
    try:
        from .transcribe import transcribe as _t, write_json
    except ImportError as e:
        raise RuntimeError("Transcription needs the whisper extra: "
                           "pip install \"voxalign[whisper]\"") from e
    segs = _t(files, names, model=model, device=device)
    write_json(segs, out_json)
    return {"segments": len(segs), "out_json": out_json}


@server.tool()
def voxalign_energy(transcript_path: str, bleed_json_path: str, files: list[str],
                    names: list[str], out_path: str, margin: float = 1.20) -> dict:
    """Resolve leftover crosstalk blocks (S?) by energy. Locate each unresolved
    block on the raw timeline via the ungated (bleed) transcripts, then attribute it
    to the loudest mic at that moment. Genuine simultaneous overlap is left S?.
    Writes the updated transcript to out_path. Requires ffmpeg. Returns how many were
    resolved and a per-block report."""
    if len(files) != len(names):
        raise ValueError("files and names must be the same length (one name per mic).")
    _need(transcript_path, bleed_json_path, *files)
    from .energy import energy_tiebreak
    blocks = parse_attributed(transcript_path)
    bleed = load_raw(bleed_json_path)
    report = energy_tiebreak(blocks, bleed, files, names, margin=margin)
    with open(out_path, "w", encoding="utf-8") as fh:
        for b in blocks:
            tag = " [energy]" if b.get("energy") else (
                " [inferred]" if b.get("inferred") else "")
            fh.write(f"{b['start']}\n{(b['spk'] or 'S?')}: {b['text']}{tag}\n\n")
    resolved = sum(1 for r in report if r["result"] != "S?")
    return {"resolved": resolved, "still_unresolved": len(report) - resolved,
            "out_path": out_path, "report": report}


@server.tool()
def voxalign_run(files: list[str], names: list[str], edited_srt_path: str,
                 out_path: str, model: str = "base.en", device: str | None = None,
                 workdir: str | None = None, min_run: int = 3,
                 gate_margin: float = 1.25, energy_margin: float = 1.20) -> dict:
    """Full pipeline: gate the mics, transcribe the gated and raw channels, reconcile
    onto the edited SRT, then energy-tiebreak the crosstalk. Writes the final
    attributed transcript to out_path. Requires ffmpeg and the [whisper] extra."""
    if len(files) != len(names):
        raise ValueError("files and names must be the same length (one name per mic).")
    _need(edited_srt_path, *files)
    import json
    from .gate import gate as _gate
    from .energy import energy_tiebreak
    try:
        from .transcribe import transcribe as _t
    except ImportError as e:
        raise RuntimeError("Full pipeline needs the whisper extra: "
                           "pip install \"voxalign[whisper]\"") from e

    tmp = workdir or (out_path + ".voxalign")
    gated_dir = os.path.join(tmp, "gated")
    os.makedirs(gated_dir, exist_ok=True)
    _gate(files, names, gated_dir, margin=gate_margin)
    gated_files = [os.path.join(gated_dir, n + ".wav") for n in names]

    clean = _t(gated_files, names, model=model, device=device)
    bleed = _t(files, names, model=model, device=device)
    json.dump(bleed, open(os.path.join(tmp, "bleed.json"), "w", encoding="utf-8"))

    blocks = parse_edited(edited_srt_path)
    _reconcile(clean, blocks, min_run=min_run)
    energy_tiebreak(blocks, bleed, files, names, margin=energy_margin)
    write_transcript(blocks, out_path)
    remaining = sum(1 for b in blocks if not b["spk"])
    return {"blocks": len(blocks), "unresolved": remaining, "out_path": out_path}


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
