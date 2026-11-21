#!/usr/bin/env python3
"""Smoke test: imports, dataset tokenize, short train, Gradio build."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    print("PROJECT_ROOT", ROOT)
    from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote
    from model_symbolic.bass_groove_model import (
        BassGrooveModel,
        generate_bass_line,
        load_checkpoint,
    )
    from data_prep.pipeline import AudioPrepPipeline, parse_time_signature
    from data_prep.build_dataset import build_dataset, encode_sample, synthetic_bootstrap_samples

    assert parse_time_signature("7/8") == (7, 8)

    # Tiny synthetic sample encode path
    samples = synthetic_bootstrap_samples(n_songs=1, max_steps=64, seed=1)
    assert samples and "tokens" in samples[0]
    print(f"synthetic encode OK ({len(samples)} aug samples)")

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
    assert len(notes) > 0
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

    # Build dataset (synthetic) + 1-epoch train dry-run
    processed = ROOT / "dataset" / "processed"
    data_path = build_dataset(
        raw_dir=ROOT / "dataset" / "raw_songs",
        processed_dir=processed,
        allow_synthetic=True,
        max_steps=64,
        transpose=True,
    )
    assert data_path.exists()
    print("train_data.pt", data_path, "size", data_path.stat().st_size)

    from model_symbolic.train import run_training

    ckpt = ROOT / "checkpoints" / "best_bass_model.pt"
    run_training(
        data_path=data_path,
        epochs=1,
        batch_size=8,
        device="cpu",
        out_ckpt=ckpt,
    )
    assert ckpt.exists()
    model = BassGrooveModel()
    load_checkpoint(model, ckpt)
    print("checkpoint load OK", ckpt)

    # Optional: tiny wav tokenize via pipeline (no demucs required)
    try:
        import numpy as np
        import soundfile as sf

        wav = Path(td) if False else ROOT / "dataset" / "cache" / "_smoke_tone.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        sr = 22050
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        tone = 0.2 * np.sin(2 * np.pi * 110.0 * t).astype(np.float32)
        sf.write(str(wav), tone, sr)
        pipe = AudioPrepPipeline(sample_rate=sr)
        onsets = pipe.analyze_drums_only(wav)
        print("tiny wav onsets kick/snare", len(onsets.kick_ms), len(onsets.snare_ms))
    except Exception as exc:  # noqa: BLE001
        print("tiny wav skipped:", exc)

    from web_ui.app import build_ui, resolve_checkpoint, MODEL_RULES, MODEL_BEST

    assert resolve_checkpoint(MODEL_RULES)[1] is True
    path, force = resolve_checkpoint(MODEL_BEST)
    assert path == ckpt and force is False
    demo = build_ui()
    assert demo is not None
    print("gradio UI build OK")
    print("core imports OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
