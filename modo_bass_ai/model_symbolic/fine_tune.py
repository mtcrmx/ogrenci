"""Fine-tune best_bass_model.pt on user MIDI walks in dataset/custom_midi.

Usage:
  python -m model_symbolic.fine_tune
  python -m model_symbolic.fine_tune --midi-dir "/path/to/Yuruyus Veri Seti" --lr 1e-5
  MODO_CUSTOM_MIDI_DIR=... python -m model_symbolic.fine_tune
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional, Sequence

import numpy as np
import pretty_midi
import torch
from torch.utils.data import DataLoader

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data_prep.build_dataset import encode_sample  # noqa: E402
from model_symbolic.bass_groove_model import (  # noqa: E402
    PAD_ID,
    PITCH_MAX,
    PITCH_MIN,
    REST_ID,
    BassGrooveModel,
    load_checkpoint,
)
from model_symbolic.train import (  # noqa: E402
    DEFAULT_LOSS_WEIGHTS,
    TensorGrooveDataset,
    collate,
    compute_multitask_loss,
    resolve_device,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fine_tune")

BEST_CKPT = _ROOT / "checkpoints" / "best_bass_model.pt"
CUSTOM_CKPT = _ROOT / "checkpoints" / "custom_style_bass.pt"
DEFAULT_MIDI_DIR = _ROOT / "dataset" / "custom_midi"


def list_midi_files(midi_dir: Path) -> List[Path]:
    if not midi_dir.exists():
        return []
    return sorted(
        p
        for p in midi_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".mid", ".midi"}
    )


def midi_to_sample(path: Path, max_steps: int = 256, play_style: str = "Fingerstyle") -> dict:
    """Convert a bass MIDI walk into one training sample dict."""
    pm = pretty_midi.PrettyMIDI(str(path))
    notes_pm: List[pretty_midi.Note] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        notes_pm.extend(inst.notes)
    if not notes_pm:
        # fall back to any notes including drums track misuse
        for inst in pm.instruments:
            notes_pm.extend(inst.notes)
    if not notes_pm:
        raise ValueError(f"No notes in {path}")

    notes_pm.sort(key=lambda n: n.start)
    bass_notes = []
    for n in notes_pm:
        pitch = int(np.clip(n.pitch, PITCH_MIN, PITCH_MAX))
        # fold octaves into bass range if needed
        while pitch > PITCH_MAX:
            pitch -= 12
        while pitch < PITCH_MIN:
            pitch += 12
        bass_notes.append(
            {
                "start_ms": float(n.start * 1000.0),
                "end_ms": float(n.end * 1000.0),
                "pitch": pitch,
                "velocity": int(n.velocity),
                "pitch_bend": 0.0,
            }
        )

    # Estimate BPM from PrettyMIDI; default 100
    tempi = pm.get_tempo_changes()[1]
    bpm = float(tempi[0]) if len(tempi) else 100.0
    if not math.isfinite(bpm) or bpm < 40 or bpm > 240:
        bpm = 100.0

    # Simple chord guess from pitch-class histogram per bar
    duration_ms = max(n["end_ms"] for n in bass_notes)
    bar_ms = (60_000.0 / bpm) * 4.0
    n_bars = max(1, int(math.ceil(duration_ms / bar_ms)))
    pc_names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    chords: List[str] = []
    for b in range(n_bars):
        t0, t1 = b * bar_ms, (b + 1) * bar_ms
        hist = np.zeros(12, dtype=np.float32)
        for n in bass_notes:
            if n["start_ms"] >= t0 and n["start_ms"] < t1:
                hist[int(n["pitch"]) % 12] += max(1.0, n["velocity"] / 64.0)
        root = int(np.argmax(hist)) if hist.sum() > 0 else 0
        # minor if flat-3 stronger than major 3
        maj3 = hist[(root + 4) % 12]
        min3 = hist[(root + 3) % 12]
        qual = "m" if min3 > maj3 else ""
        chords.append(pc_names[root] + qual)

    # Sparse synthetic kick on downbeats for conditioning
    kick = [b * bar_ms for b in range(n_bars)]
    snare = [b * bar_ms + bar_ms / 2 for b in range(n_bars)]

    sample = encode_sample(
        bass_notes,
        chords,
        bpm,
        "4/4",
        kick,
        snare,
        play_style=play_style,
        max_steps=max_steps,
    )
    sample["song_id"] = path.stem
    sample["source_midi"] = str(path)
    return sample


def build_midi_samples(
    midi_dir: Path,
    max_steps: int = 256,
    log: Callable[[str], None] = logger.info,
) -> List[dict]:
    files = list_midi_files(midi_dir)
    if not files:
        raise FileNotFoundError(
            f"No .mid/.midi under {midi_dir}. "
            "Copy your 'Yuruyus Veri Seti' MIDI walks here or pass --midi-dir."
        )
    samples: List[dict] = []
    for f in files:
        try:
            samples.append(midi_to_sample(f, max_steps=max_steps))
            log(f"[midi] {f.name}")
        except Exception as exc:  # noqa: BLE001
            log(f"[skip] {f.name}: {exc}")
    if not samples:
        raise RuntimeError("No usable MIDI samples.")
    log(f"Fine-tune set: {len(samples)} file(s) from {midi_dir}")
    return samples


def run_fine_tune(
    midi_dir: Optional[Path] = None,
    base_ckpt: Path = BEST_CKPT,
    out_ckpt: Path = CUSTOM_CKPT,
    epochs: int = 8,
    batch_size: int = 8,
    lr: float = 1e-5,
    device: str = "auto",
    max_steps: int = 256,
    log: Callable[[str], None] = logger.info,
) -> Path:
    midi_dir = Path(midi_dir or DEFAULT_MIDI_DIR)
    device = resolve_device(device)
    samples = build_midi_samples(midi_dir, max_steps=max_steps, log=log)

    ds = TensorGrooveDataset(samples)
    loader = DataLoader(
        ds, batch_size=min(batch_size, max(1, len(ds))), shuffle=True, collate_fn=collate
    )

    model = BassGrooveModel().to(device)
    if Path(base_ckpt).exists():
        load_checkpoint(model, base_ckpt, map_location=device)
        log(f"Loaded base weights from {base_ckpt}")
    else:
        log(f"WARNING: {base_ckpt} missing — fine-tuning from random init.")

    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    out_ckpt = Path(out_ckpt)
    out_ckpt.parent.mkdir(parents=True, exist_ok=True)
    best = float("inf")

    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        n = 0
        for batch in loader:
            tokens = batch["tokens"].to(device)
            inp = tokens.clone()
            inp[:, 1:] = tokens[:, :-1]
            inp[:, 0] = REST_ID
            style = batch["style"].to(device)
            meter = batch["meter"].to(device)
            vels = batch["vels"].to(device)
            micro = batch.get("micro_ms")
            micro = torch.zeros_like(vels) if micro is None else micro.to(device)
            pad_mask = tokens == PAD_ID
            out = model(
                inp,
                style,
                batch["drum"].to(device),
                batch["chord"].to(device),
                meter,
                src_key_padding_mask=pad_mask,
            )
            loss, _ = compute_multitask_loss(
                out, tokens, vels, micro, style, meter, weights=DEFAULT_LOSS_WEIGHTS
            )
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.item())
            n += 1
        avg = total / max(n, 1)
        log(f"fine-tune epoch {epoch}/{epochs}  loss={avg:.4f}  lr={lr}")
        if avg < best:
            best = avg
            model.save(out_ckpt)
            log(f"  ↳ saved {out_ckpt}")

    if not out_ckpt.exists():
        model.save(out_ckpt)
    log(f"Fine-tune done → {out_ckpt}")
    return out_ckpt


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune bass model on custom MIDI")
    parser.add_argument(
        "--midi-dir",
        type=str,
        default="",
        help="Folder of .mid walks (default dataset/custom_midi or MODO_CUSTOM_MIDI_DIR)",
    )
    parser.add_argument("--base", type=str, default=str(BEST_CKPT))
    parser.add_argument("--out", type=str, default=str(CUSTOM_CKPT))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()

    midi = args.midi_dir or os.environ.get("MODO_CUSTOM_MIDI_DIR", "")
    run_fine_tune(
        midi_dir=Path(midi) if midi else DEFAULT_MIDI_DIR,
        base_ckpt=Path(args.base),
        out_ckpt=Path(args.out),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
    )


if __name__ == "__main__":
    main()
