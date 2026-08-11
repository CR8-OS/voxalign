from voxalign.reconcile import parse_edited, reconcile, build_raw_stream
from voxalign.audio import norm_tokens


def test_parse_smpte(tmp_path):
    p = tmp_path / "e.txt"
    p.write_text("00:00:01:00 - 00:00:03:00\nHello there friend\n\n"
                 "00:00:03:00 - 00:00:05:00\nGeneral Kenobi\n", encoding="utf-8")
    b = parse_edited(str(p))
    assert len(b) == 2
    assert b[0]["text"] == "Hello there friend"


def test_parse_srt(tmp_path):
    p = tmp_path / "e.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello there friend\n\n"
                 "2\n00:00:03,000 --> 00:00:05,000\nGeneral Kenobi\n", encoding="utf-8")
    b = parse_edited(str(p))
    assert len(b) == 2 and b[1]["text"] == "General Kenobi"


def test_reconcile_handles_reordering(tmp_path):
    # Cold-open style: edited order differs from raw speaking order.
    raw = [
        {"start": 0.0, "end": 2.0, "spk": "A", "text": "the quick brown fox"},
        {"start": 2.0, "end": 4.0, "spk": "B", "text": "jumps over the lazy dog"},
        {"start": 4.0, "end": 6.0, "spk": "A", "text": "and then it runs away fast"},
    ]
    edited = tmp_path / "e.txt"
    edited.write_text(
        "00:00:04:00 - 00:00:06:00\nand then it runs away fast\n\n"   # A (moved up)
        "00:00:00:00 - 00:00:02:00\nthe quick brown fox\n\n"          # A
        "00:00:02:00 - 00:00:04:00\njumps over the lazy dog\n",       # B
        encoding="utf-8")
    blocks = parse_edited(str(edited))
    stats = reconcile(raw, blocks)
    assert [b["spk"] for b in blocks] == ["A", "A", "B"]
    assert stats["matched"] == 3


def test_context_fill(tmp_path):
    raw = [
        {"start": 0.0, "end": 2.0, "spk": "A", "text": "alpha alpha alpha alpha"},
        {"start": 2.0, "end": 4.0, "spk": "A", "text": "gamma gamma gamma gamma"},
    ]
    edited = tmp_path / "e.txt"
    edited.write_text(
        "00:00:00:00 - 00:00:02:00\nalpha alpha alpha alpha\n\n"
        "00:00:02:00 - 00:00:02:50\nzzz\n\n"                      # no match -> fill
        "00:00:03:00 - 00:00:04:00\ngamma gamma gamma gamma\n",
        encoding="utf-8")
    blocks = parse_edited(str(edited))
    reconcile(raw, blocks)
    assert blocks[1]["spk"] == "A" and blocks[1]["inferred"] is True
