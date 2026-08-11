"""VoxAlign: voice-attribution SRT reconciler.

Take per-channel (per-mic) recordings plus a final edited SRT/caption file and
produce an accurate, speaker-attributed transcript. Four stages:

  gate       remove mic bleed by keeping each channel only where it is loudest
  transcribe per-channel ASR (optional extra; bring your own if you prefer)
  reconcile  text-align each channel onto the edited caption timeline
  energy     resolve leftover crosstalk blocks by the loudest mic

The invention is gate + reconcile + energy; transcription is swappable.
"""
__version__ = "0.2.0"
