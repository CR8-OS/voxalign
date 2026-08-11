# VoxAlign

**Voice-attribution SRT reconciler.** Turn per-channel (per-mic) recordings plus a
final edited SRT/caption file into an accurate, speaker-attributed transcript.

If you record a panel or podcast with one isolated mic per person, every mic still
bleeds the whole room, so naive "one channel = one speaker" attribution collapses.
VoxAlign fixes that with energy, not guesswork, and aligns the result onto the
caption file your editor already cut.

No cloud, no diarization model, no per-minute fees. It runs locally.

## How it works

Four stages, and only the middle one is a commodity you can swap:

1. **Gate**: for each short frame the true speaker is the *loudest* mic. Keep each
   channel only where it dominates; silence the rest. Kills bleed.
2. **Transcribe**: run any ASR per gated channel. A `faster-whisper` path ships as
   an optional extra; or bring your own transcripts as JSON.
3. **Reconcile**: match each edited caption block independently across the
   per-channel text, so reordering (a cold open) and small edits are handled.
4. **Energy tiebreak**: blocks lost to crosstalk get located on the raw timeline
   via the ungated transcripts, then attributed to the loudest mic. Genuine
   simultaneous overlap is left flagged rather than guessed.

On a real 38-minute, 4-mic episode this attributed **520 of 523 caption blocks
(99.4%)**, leaving only inaudible one-word fragments for a human.

## Install

```bash
pip install voxalign            # core: gate + reconcile + energy
pip install "voxalign[whisper]" # add the faster-whisper transcription path
```

Requires `ffmpeg` on your PATH.

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

Bring-your-own transcripts: skip stage 2. `--raw` / `--bleed` just need a JSON list
of `{"start": <sec>, "end": <sec>, "spk": "<name>", "text": "..."}`.

Output blocks carry a tag so you can see how each was decided: `[energy]` (loudest
mic), `[inferred]` (both confident neighbours agreed), or none (direct text match).
Unresolved blocks are labelled `S?`.

## Tuning

- `--gate-margin` / gate `--margin` (default 1.25): how much louder the dominant mic
  must be. Higher = stricter, more silence, fewer false attributions.
- `--energy-margin` (default 1.20): confidence needed to break a crosstalk tie.
- `--min-run` (default 3): shortest word run that counts as a text match.

## Support

VoxAlign is free and open source (MIT). If it saved you time, tips are welcome via
the Sponsor button on this repo. Not required, always appreciated.

## License

MIT © Christophe Jammet
