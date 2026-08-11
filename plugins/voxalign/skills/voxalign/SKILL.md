---
name: voxalign
description: Turn per-channel (per-mic) recordings plus a final edited SRT/caption file into an accurate speaker-attributed transcript. Use when you have isolated per-speaker audio tracks and an edited caption file and need to know who said each line, especially for panels and podcasts where mics bleed and naive per-channel attribution fails. Wraps the voxalign CLI (gate, transcribe, reconcile, energy, run).
---

# VoxAlign skill

Produce a speaker-attributed transcript from per-channel mics + an edited SRT.

## When to use
- One isolated mic per speaker (multitrack), and a final edited caption file with
  no speaker labels.
- Mic bleed makes "one channel = one speaker" unreliable.

## Install
`pip install "voxalign[whisper]"` (or plain `voxalign` if you bring your own
per-channel transcripts). Requires ffmpeg.

## Fastest path
```
voxalign run --files "<mic1>,<mic2>,..." --names "<Name1>,<Name2>,..." \
             --edited <edited.srt> --out <attributed.txt>
```

## Stage by stage (when you want control or already transcribed)
1. `voxalign gate --files ... --names ... --out gated/`: remove bleed.
2. `voxalign transcribe --files gated/*.wav --names ... --out clean.json`: per
   channel ASR. Skip if you already have transcripts.
3. `voxalign reconcile --raw clean.json --edited <edited.srt> --out draft.txt`.
4. `voxalign energy --transcript draft.txt --bleed bleed.json --files ... --names ...
   --out final.txt`: resolve crosstalk by loudest mic.

## Reading the output
Each block is `Speaker: text` with an optional tag: `[energy]` resolved by loudest
mic, `[inferred]` filled from agreeing neighbours, none = direct text match. `S?` =
genuinely unresolved (true overlap or inaudible); hand those to a person.

## Notes
- `--gate-margin` / `--energy-margin` trade strictness against coverage.
- Bring-your-own transcripts must be JSON: `[{"start","end","spk","text"}, ...]`.
