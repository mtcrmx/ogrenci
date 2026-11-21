#!/usr/bin/env python3
"""Quick smoke test: imports, rule generation, MIDI write, Gradio build."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    print("PROJECT_ROOT", ROOT)
    from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote
    from model_symbolic.bass_groove_model import generate_bass_line, BassGrooveModel
    from data_prep.pipeline import AudioPrepPipeline, parse_time_signature

    assert parse_time_signature("7/8") == (7, 8)
    notes = generate_bass_line(
        "Am7 | D9 | Gmaj7 | Cmaj7",
        bpm=100,
        time_signature="4/4",
        play_style="Fingerstyle",
        humanize_ms=10,
        groove_amount=0.6,
        seed=42,
        force_rules=True,
    )
    assert len(notes) > 0, "expected generated notes"
    print(f"generated {len(notes)} notes")

    eng = ArticulationEngine(ROOT / "config" / "modo_bass_map.json")
    melody = [
        BassMelodyNote(
            start_ms=n.start_ms,
            end_ms=n.end_ms,
            pitch=n.pitch,
            velocity=n.velocity,
            articulation=n.articulation,
            is_passing=n.is_passing,
        )
        for n in notes
    ]
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "smoke.mid"
        eng.write_midi(melody, out, play_style="Fingerstyle")
        assert out.exists() and out.stat().st_size > 0
        print("midi bytes", out.stat().st_size)

    _ = BassGrooveModel()
    _ = AudioPrepPipeline()
    print("core imports OK")

    from web_ui.app import build_ui

    demo = build_ui()
    assert demo is not None
    print("gradio UI build OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
