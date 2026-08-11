"""Stage 2 (optional): per-channel transcription with faster-whisper.

This is the swappable part. If you already have per-channel transcripts as JSON
(a list of {start, end, spk, text}), skip this entirely. Requires the [whisper]
extra: pip install voxalign[whisper].

On Windows + NVIDIA, faster-whisper loads cublas/cudnn at runtime via ctranslate2
(not torch), so we prepend the pip-installed NVIDIA lib dirs to PATH at import.
"""
from __future__ import annotations
import json
import os


def _prepare_cuda_dlls() -> None:
    try:
        import nvidia  # namespace package
        dirs = []
        for base in list(getattr(nvidia, "__path__", [])):
            for sub in ("cublas", "cudnn", "cuda_nvrtc"):
                d = os.path.join(base, sub, "bin")
                if os.path.isdir(d):
                    dirs.append(d)
                    try:
                        os.add_dll_directory(d)
                    except Exception:
                        pass
        if dirs:
            os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def detect_device() -> str:
    try:
        import ctranslate2
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def transcribe(
    files: list[str],
    names: list[str],
    model: str = "base.en",
    device: str | None = None,
    vad: bool = True,
) -> list[dict]:
    """Transcribe each channel; return a merged, speaker-attributed segment list.

    The speaker label for a channel is its provided name (ground truth from the
    isolated mic).
    """
    _prepare_cuda_dlls()
    from faster_whisper import WhisperModel

    device = device or detect_device()
    compute = "float16" if device == "cuda" else "int8"
    print(f"Loading {model} on {device} ...")
    wm = WhisperModel(model, device=device, compute_type=compute)

    segments: list[dict] = []
    for i, (f, name) in enumerate(zip(files, names), 1):
        print(f"[{i}/{len(files)}] {os.path.basename(f)}  ->  {name}")
        segs, _info = wm.transcribe(f, vad_filter=vad, language="en"
                                    if model.endswith(".en") else None)
        for s in segs:
            text = s.text.strip()
            if text:
                segments.append({"start": float(s.start), "end": float(s.end),
                                 "spk": name, "text": text})
    segments.sort(key=lambda s: s["start"])
    print(f"Merged {len(segments)} segments across {len(files)} channels.")
    return segments


def write_json(segments: list[dict], path: str) -> None:
    json.dump(segments, open(path, "w", encoding="utf-8"), indent=2)
