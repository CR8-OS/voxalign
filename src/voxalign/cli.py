"""VoxAlign command-line interface.

Subcommands:
  gate        raw mics            -> gated wavs
  transcribe  gated/raw wavs      -> attributed JSON      (needs [whisper])
  reconcile   attributed JSON+SRT -> speaker transcript
  energy      transcript+bleed    -> resolve crosstalk
  run         raw mics + SRT      -> finished transcript  (full pipeline)
"""
from __future__ import annotations
import argparse
import json
import os
import sys

from . import __version__
from .reconcile import parse_edited, reconcile, write_transcript, load_raw


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def cmd_gate(a):
    from .gate import gate
    stats = gate(_split(a.files), _split(a.names), a.out,
                 margin=a.margin, smooth=a.smooth, floor_pctl=a.floor_pctl)
    for k, v in stats.items():
        print(f"  {k:10} {v:6.1f} min")


def cmd_transcribe(a):
    from .transcribe import transcribe, write_json
    segs = transcribe(_split(a.files), _split(a.names), model=a.model, device=a.device)
    write_json(segs, a.out)
    print("wrote", a.out)


def cmd_reconcile(a):
    raw = load_raw(a.raw)
    blocks = parse_edited(a.edited)
    stats = reconcile(raw, blocks, min_run=a.min_run)
    write_transcript(blocks, a.out)
    print(f"blocks: {len(blocks)}  matched: {stats['matched']}  "
          f"filled: {stats['filled']}  remaining: {stats['remaining']}")


def _parse_transcript(path):
    import re
    blocks = []
    for chunk in open(path, encoding="utf-8").read().split("\n\n"):
        ls = [l for l in chunk.split("\n") if l.strip()]
        if len(ls) >= 2:
            m = re.match(r"^(\S+):\s*(.*)$", ls[1])
            txt = m.group(2)
            spk = m.group(1)
            for t in (" [energy]", " [inferred]", " [confirmed]"):
                txt = txt.replace(t, "")
            blocks.append({"start": ls[0].split(" ")[0], "end": "",
                           "raw_tc": ls[0],
                           "spk": None if spk == a_unknown else spk,
                           "text": txt,
                           "inferred": "[inferred]" in ls[1],
                           "energy": "[energy]" in ls[1]})
    return blocks


a_unknown = "S?"


def cmd_energy(a):
    from .energy import energy_tiebreak
    blocks = _parse_transcript(a.transcript)
    for b in blocks:
        b["start"] = b["raw_tc"]
    bleed = load_raw(a.bleed)
    report = energy_tiebreak(blocks, bleed, _split(a.files), _split(a.names),
                             margin=a.margin)
    with open(a.out, "w", encoding="utf-8") as fh:
        for b in blocks:
            tag = " [energy]" if b.get("energy") else (
                " [inferred]" if b.get("inferred") else "")
            fh.write(f"{b['raw_tc']}\n{(b['spk'] or a_unknown)}: {b['text']}{tag}\n\n")
    resolved = sum(1 for r in report if r["result"] != "S?")
    if a.report:
        json.dump(report, open(a.report, "w", encoding="utf-8"), indent=2)
    print(f"energy resolved: {resolved}   still S?: {len(report) - resolved}")


def cmd_run(a):
    from .gate import gate
    from .transcribe import transcribe
    from .energy import energy_tiebreak
    files, names = _split(a.files), _split(a.names)
    tmp = a.workdir or (a.out + ".voxalign")
    os.makedirs(tmp, exist_ok=True)

    gated_dir = os.path.join(tmp, "gated")
    gate(files, names, gated_dir, margin=a.gate_margin)
    gated_files = [os.path.join(gated_dir, n + ".wav") for n in names]

    clean = transcribe(gated_files, names, model=a.model, device=a.device)
    bleed = transcribe(files, names, model=a.model, device=a.device)
    json.dump(bleed, open(os.path.join(tmp, "bleed.json"), "w", encoding="utf-8"))

    blocks = parse_edited(a.edited)
    reconcile(clean, blocks, min_run=a.min_run)
    energy_tiebreak(blocks, bleed, files, names, margin=a.energy_margin)
    write_transcript(blocks, a.out)
    remaining = sum(1 for b in blocks if not b["spk"])
    print(f"done -> {a.out}  ({len(blocks)} blocks, {remaining} left S?)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="voxalign", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"voxalign {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gate", help="raw mics -> gated wavs")
    g.add_argument("--files", required=True); g.add_argument("--names", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--margin", type=float, default=1.25)
    g.add_argument("--smooth", type=int, default=9)
    g.add_argument("--floor-pctl", dest="floor_pctl", type=float, default=45.0)
    g.set_defaults(func=cmd_gate)

    t = sub.add_parser("transcribe", help="wavs -> attributed JSON (needs [whisper])")
    t.add_argument("--files", required=True); t.add_argument("--names", required=True)
    t.add_argument("--out", required=True); t.add_argument("--model", default="base.en")
    t.add_argument("--device", default=None); t.set_defaults(func=cmd_transcribe)

    r = sub.add_parser("reconcile", help="attributed JSON + edited SRT -> transcript")
    r.add_argument("--raw", required=True); r.add_argument("--edited", required=True)
    r.add_argument("--out", required=True); r.add_argument("--min-run", type=int, default=3)
    r.set_defaults(func=cmd_reconcile)

    e = sub.add_parser("energy", help="resolve leftover S? blocks by loudest mic")
    e.add_argument("--transcript", required=True); e.add_argument("--bleed", required=True)
    e.add_argument("--files", required=True); e.add_argument("--names", required=True)
    e.add_argument("--out", required=True); e.add_argument("--report", default=None)
    e.add_argument("--margin", type=float, default=1.20); e.set_defaults(func=cmd_energy)

    rn = sub.add_parser("run", help="full pipeline: raw mics + SRT -> transcript")
    rn.add_argument("--files", required=True); rn.add_argument("--names", required=True)
    rn.add_argument("--edited", required=True); rn.add_argument("--out", required=True)
    rn.add_argument("--workdir", default=None); rn.add_argument("--model", default="base.en")
    rn.add_argument("--device", default=None); rn.add_argument("--min-run", type=int, default=3)
    rn.add_argument("--gate-margin", type=float, default=1.25)
    rn.add_argument("--energy-margin", type=float, default=1.20)
    rn.set_defaults(func=cmd_run)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
