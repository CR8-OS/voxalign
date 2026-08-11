# Changelog

All notable changes to VoxAlign are documented here.

## [0.2.0] - 2026-08-11

- MCP server (`voxalign-mcp`): exposes gate, transcribe, reconcile, energy, and the
  full run as MCP tools, so any MCP client (Claude Code, Cowork, IBM Bob) can drive
  VoxAlign. Optional extra: `pip install "voxalign[mcp]"`. Imports the package
  directly, one codebase behind the CLI, the Claude plugin, and MCP.

## [0.1.0] - 2026-08-11

Initial release.

- `gate`: dominant-energy bleed removal across per-channel mics.
- `transcribe`: optional per-channel faster-whisper path (CUDA-aware on Windows).
- `reconcile`: independent per-block text alignment onto an edited SMPTE/SRT file,
  with unanimous-neighbour context fill.
- `energy`: crosstalk tiebreak by loudest mic on the raw timeline.
- `run`: full pipeline end to end.

Validated on a real 38-minute, 4-mic episode: 520 / 523 blocks attributed (99.4%).
