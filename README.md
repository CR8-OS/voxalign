# VoxAlign

[![CI](https://github.com/CR8-OS/voxalign/actions/workflows/ci.yml/badge.svg)](https://github.com/CR8-OS/voxalign/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-buy%20me%20a%20coffee-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/cj48744)
[![Add to Claude](https://img.shields.io/badge/Cowork-add%20plugin-6E56CF)](#as-a-claude-plugin)

**Voice-attribution SRT reconciler.** Turn per-channel (per-mic) recordings plus a final edited SRT into an accurate, speaker-attributed transcript.

I've spent the year or so (among other things) building AI-enabled process tooling for the likes of IBM, which is a polite way of saying I've spent a lot of time staring at the parts of content and media production processes that make even seasoned producers and editors quietly lose their minds. Most of those parts are invisible. A handoff here, a file format there, a single step that quietly eats an afternoon. Podcast transcripts are one of the worst offenders, and speaker attribution is the piece that finally broke me.

Here's the problem: You record every guest on a separate mic, everything is clean and beautifully isolated, life is good. Then you cut the episode, flatten it to a final mix, and all that lovely per-channel separation evaporates. You are left holding a pristine SRT and no reliable idea of who actually said what. I burned through a lot of trials, tribulations, and mediocre workarounds trying to pull a clean, attributed transcript back out of that final file.

VoxAlign is the tool I wanted to exist. It takes the raw per-mic capture from Riverside, or wherever you record your channels, transcribes each channel on its own, and reconciles those transcripts against your final edited SRT. The channels know who is speaking. The edit knows the final words and timing. VoxAlign just marries the two.

And yes, there are paid tools like Trint that throw AI at the who-said-what problem and charge you handsomely for the guesswork. I think this is the more elegant and more foolproof path. It leans on lightweight, free, open-source transcription (you pick the engine) and spends its cleverness on a better process instead of a bigger model. Higher accuracy, zero dollars, nothing leaves your machine.

## How it works

Four stages, and only the middle one is a commodity you can swap:

1. **Gate** for each short frame the true speaker is the *loudest* mic. Keep each channel only where it dominates; silence the rest. Kills bleed.
2. **Transcribe** run any ASR per gated channel. A `faster-whisper` path ships as an optional extra; or bring your own transcripts as JSON.
3. **Reconcile** match each edited caption block independently across the per-channel text, so reordering (a cold open) and small edits are handled.
4. **Energy tiebreak** blocks lost to crosstalk get located on the raw timeline via the ungated transcripts, then attributed to the loudest mic. Genuine simultaneous overlap is left flagged rather than guessed.

On a real 38-minute, 4-mic episode this attributed **520 of 523 caption blocks (99.4%)**, leaving only inaudible one-word fragments for a human.

## Install

Two ways in: the command-line tool, or as a Cowork / Claude Code plugin. Both want `ffmpeg` on your PATH.

### As a CLI (pip)

Until it lands on PyPI, install straight from the repo.

```bash
pip install "voxalign @ git+https://github.com/CR8-OS/voxalign"            # core
pip install "voxalign[whisper] @ git+https://github.com/CR8-OS/voxalign"   # + faster-whisper
```

### As a Claude plugin

From Cowork or Claude Code, add the marketplace and install:

```
/plugin marketplace add CR8-OS/voxalign
/plugin install voxalign@cr8-os
```

The plugin hands Claude the VoxAlign skill, so it knows how to drive the stages. The transcription itself still runs through the pip package above, so install that too when you want turnkey processing.

### As an MCP server (Claude Code, Cowork, IBM Bob, any MCP client)

VoxAlign also runs as an MCP server, exposing each stage as a tool.

```bash
pip install "voxalign[mcp]"          # add [whisper] too for the transcribe tool
```

Register it with your client. For a `.mcp.json`:

```json
{
  "mcpServers": {
    "voxalign": { "command": "voxalign-mcp" }
  }
}
```

Tools: `voxalign_gate`, `voxalign_transcribe`, `voxalign_reconcile`, `voxalign_energy`, and `voxalign_run` (the whole pipeline). Same engine as the CLI and the plugin, so one codebase serves them all.

## Use

Full pipeline (raw mics + edited SRT in, attributed transcript out):

```bash
voxalign run \
  --files "andrea.aif,cj.aif,jason.aif,rudy.aif" \
  --names "Andrea,CJ,Jason,Rudy" \
  --edited episode_final.srt \
  --out episode_attributed.txt
```

Or run the stages yourself:

```bash
voxalign gate       --files "a.aif,b.aif" --names "A,B" --out gated/
voxalign transcribe --files "gated/A.wav,gated/B.wav" --names "A,B" --out clean.json
voxalign reconcile  --raw clean.json --edited episode_final.srt --out draft.txt
voxalign energy     --transcript draft.txt --bleed bleed.json \
                    --files "a.aif,b.aif" --names "A,B" --out final.txt
```

Bring-your-own transcripts: skip stage 2. `--raw` / `--bleed` just need a JSON list of `{"start": <sec>, "end": <sec>, "spk": "<name>", "text": "..."}`.

Output blocks carry a tag so you can see how each was decided: `[energy]` (loudest mic), `[inferred]` (both confident neighbours agreed), or none (direct text match). Unresolved blocks are labelled `S?`.

## Tuning

- `--gate-margin` / gate `--margin` (default 1.25): how much louder the dominant mic must be. Higher = stricter, more silence, fewer false attributions.
- `--energy-margin` (default 1.20): confidence needed to break a crosstalk tie.
- `--min-run` (default 3): shortest word run that counts as a text match.

## Contributing

It takes a village, so let's make it a nice one. Comment, star, share, fork it, and send your improvements. Issues and pull requests are all welcome, from a typo fix to a whole new transcription backend.

## Support

VoxAlign is free and open source (MIT). If it saved you a headache and you feel like dropping a tip, buy me a coffee. Not required, always appreciated.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/cj48744)

## License

MIT © Christophe Jammet
