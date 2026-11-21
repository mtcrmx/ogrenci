"""Train BassGrooveModel from `dataset/processed/train_data.pt` (GPU/CPU).

Falls back to synthetic bootstrap via data_prep.build_dataset if the tensor
file is missing. Saves best weights to `checkpoints/best_bass_model.pt` and
writes a sanity-check MIDI after training.

Usage:
  python -m model_symbolic.train --epochs 5
  python -m model_symbolic.train --data dataset/processed/train_data.pt --device cuda
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, random_split

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from model_symbolic.bass_groove_model import (  # noqa: E402
    NOTE_OFFSET,
    PAD_ID,
    REST_ID,
    BassGrooveModel,
    generate_bass_line,
    load_checkpoint,
)
from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("train")

BEST_CKPT = _ROOT / "checkpoints" / "best_bass_model.pt"
DEFAULT_DATA = _ROOT / "dataset" / "processed" / "train_data.pt"
CONFIG_PATH = _ROOT / "config" / "modo_bass_map.json"
OUTPUT_DIR = _ROOT / "outputs"


class TensorGrooveDataset(Dataset):
    """Wraps list of sample dicts from train_data.pt."""

    def __init__(self, samples: List[dict]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        return self.samples[idx]


def collate(batch: List[dict]) -> dict:
    return {
        "tokens": torch.stack([b["tokens"] for b in batch]),
        "vels": torch.stack([b["vels"] for b in batch]),
        "drum": torch.stack([b["drum"] for b in batch]),
        "chord": torch.stack([b["chord"] for b in batch]),
        "meter": torch.stack([b["meter"] for b in batch]),
        "style": torch.stack([b["style"] for b in batch]),
        "length": torch.tensor([int(b["length"]) for b in batch]),
    }


def resolve_device(requested: str = "auto") -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA requested but unavailable — using CPU.")
        return "cpu"
    return requested


def load_train_payload(path: Path) -> List[dict]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(payload, dict) and "samples" in payload:
        return list(payload["samples"])
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unexpected train_data format in {path}")


def ensure_train_data(
    data_path: Path,
    raw_dir: Optional[Path] = None,
    log: Callable[[str], None] = logger.info,
) -> Path:
    if data_path.exists():
        return data_path
    log(f"{data_path} missing — building dataset (synthetic OK if raw empty)…")
    from data_prep.build_dataset import build_dataset

    return build_dataset(
        raw_dir=raw_dir or (_ROOT / "dataset" / "raw_songs"),
        processed_dir=data_path.parent,
        allow_synthetic=True,
        log=log,
    )


def train_epoch(
    model: BassGrooveModel,
    loader: DataLoader,
    opt: torch.optim.Optimizer,
    device: str,
) -> float:
    model.train()
    total = 0.0
    n = 0
    for batch in loader:
        tokens = batch["tokens"].to(device)
        inp = tokens.clone()
        inp[:, 1:] = tokens[:, :-1]
        inp[:, 0] = REST_ID
        style = batch["style"].to(device)
        drum = batch["drum"].to(device)
        chord = batch["chord"].to(device)
        meter = batch["meter"].to(device)
        pad_mask = tokens == PAD_ID

        logits, vel_pred = model(inp, style, drum, chord, meter, src_key_padding_mask=pad_mask)
        _, _, V = logits.shape
        loss_ce = F.cross_entropy(logits.reshape(-1, V), tokens.reshape(-1), ignore_index=PAD_ID)
        note_mask = tokens >= NOTE_OFFSET
        if note_mask.any():
            loss_vel = F.mse_loss(vel_pred[note_mask], batch["vels"].to(device)[note_mask]) / (
                127.0**2
            )
        else:
            loss_vel = torch.tensor(0.0, device=device)
        loss = loss_ce + 0.1 * loss_vel
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        total += float(loss.item())
        n += 1
    return total / max(n, 1)


@torch.no_grad()
def eval_loss(model: BassGrooveModel, loader: DataLoader, device: str) -> float:
    model.eval()
    total = 0.0
    n = 0
    for batch in loader:
        tokens = batch["tokens"].to(device)
        inp = tokens.clone()
        inp[:, 1:] = tokens[:, :-1]
        inp[:, 0] = REST_ID
        pad_mask = tokens == PAD_ID
        logits, vel_pred = model(
            inp,
            batch["style"].to(device),
            batch["drum"].to(device),
            batch["chord"].to(device),
            batch["meter"].to(device),
            src_key_padding_mask=pad_mask,
        )
        _, _, V = logits.shape
        loss_ce = F.cross_entropy(logits.reshape(-1, V), tokens.reshape(-1), ignore_index=PAD_ID)
        note_mask = tokens >= NOTE_OFFSET
        if note_mask.any():
            loss_vel = F.mse_loss(vel_pred[note_mask], batch["vels"].to(device)[note_mask]) / (
                127.0**2
            )
        else:
            loss_vel = torch.tensor(0.0, device=device)
        total += float((loss_ce + 0.1 * loss_vel).item())
        n += 1
    return total / max(n, 1)


def write_sample_midi(
    checkpoint: Path,
    out_dir: Path,
    log: Callable[[str], None] = logger.info,
) -> Path:
    """Generate a held-out-style sanity MIDI (ghost notes / groove check)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    chords = "Am7 | D9 | Gmaj7 | Cmaj7"
    notes = generate_bass_line(
        chords,
        bpm=100.0,
        time_signature="4/4",
        play_style="Fingerstyle",
        humanize_ms=10.0,
        groove_amount=0.7,
        checkpoint=checkpoint,
        force_rules=False,
        seed=7,
    )
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
    eng = ArticulationEngine(CONFIG_PATH)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"train_sample_{stamp}.mid"
    eng.write_midi(melody, path, play_style="Fingerstyle")
    ghosts = sum(1 for n in notes if n.articulation == "ghost" or n.velocity <= 40)
    log(f"Sample MIDI → {path} ({len(notes)} notes, ~{ghosts} ghost/low-vel)")
    return path


def run_training(
    data_path: Path = DEFAULT_DATA,
    epochs: int = 5,
    batch_size: int = 16,
    lr: float = 3e-4,
    device: str = "auto",
    out_ckpt: Path = BEST_CKPT,
    raw_dir: Optional[Path] = None,
    val_fraction: float = 0.1,
    log: Callable[[str], None] = logger.info,
) -> Path:
    device = resolve_device(device)
    data_path = ensure_train_data(Path(data_path), raw_dir=raw_dir, log=log)
    samples = load_train_payload(data_path)
    log(f"Loaded {len(samples)} samples from {data_path} | device={device}")

    ds = TensorGrooveDataset(samples)
    n_val = max(1, int(len(ds) * val_fraction)) if len(ds) > 4 else 0
    n_train = len(ds) - n_val
    if n_val > 0:
        train_ds, val_ds = random_split(
            ds, [n_train, n_val], generator=torch.Generator().manual_seed(42)
        )
    else:
        train_ds, val_ds = ds, None

    train_loader = DataLoader(
        train_ds, batch_size=min(batch_size, max(1, len(train_ds))), shuffle=True, collate_fn=collate
    )
    val_loader = (
        DataLoader(val_ds, batch_size=min(batch_size, max(1, len(val_ds))), collate_fn=collate)
        if val_ds is not None
        else None
    )

    model = BassGrooveModel().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    best = float("inf")
    out_ckpt = Path(out_ckpt)
    out_ckpt.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        tr = train_epoch(model, train_loader, opt, device)
        if val_loader is not None:
            va = eval_loss(model, val_loader, device)
            metric = va
            log(f"epoch {epoch}/{epochs}  train_loss={tr:.4f}  val_loss={va:.4f}")
        else:
            metric = tr
            log(f"epoch {epoch}/{epochs}  train_loss={tr:.4f}")
        if metric < best:
            best = metric
            model.save(out_ckpt)
            log(f"  ↳ saved best → {out_ckpt} (loss={best:.4f})")

    if not out_ckpt.exists():
        model.save(out_ckpt)
        log(f"saved final → {out_ckpt}")

    sample = write_sample_midi(out_ckpt, OUTPUT_DIR, log=log)
    log(f"Training done. Best checkpoint: {out_ckpt}")
    log(f"Sanity MIDI: {sample}")
    return out_ckpt


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MODO bass groove model")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--out", type=str, default=str(BEST_CKPT))
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="",
        help="Optional override for dataset/raw_songs (or MODO_RAW_SONGS_DIR env)",
    )
    args = parser.parse_args()

    import os

    raw = args.raw_dir or os.environ.get("MODO_RAW_SONGS_DIR", "")
    run_training(
        data_path=Path(args.data),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
        out_ckpt=Path(args.out),
        raw_dir=Path(raw) if raw else None,
    )


if __name__ == "__main__":
    main()
