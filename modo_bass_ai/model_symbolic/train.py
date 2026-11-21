"""Train BassGrooveModel from `dataset/processed/train_data.pt` (GPU/CPU).

Multi-task objective (configurable weights via ``LossWeights`` / CLI):
  * **Pitch** — Cross-Entropy over pitch tokens (incl. rest/pad ignore)
  * **Keyswitch** — Cross-Entropy over MODO BASS articulation / KS classes
  * **Micro-timing & duration** — Smooth L1 (Huber) on ms groove offsets + note lengths
  * **Velocity** — MSE so ghost notes / accents stay non-robotic

Epoch-end musical metrics (console + Gradio Eğitim Merkezi log stream):
  * Akor Uyum Oranı (% In-Chord Notes)
  * Davul Kick Kilidi Oranı (% Kick-Lock Accuracy)

Falls back to synthetic bootstrap via data_prep.build_dataset if the tensor
file is missing. Saves best weights to `checkpoints/best_bass_model.pt`.

Usage:
  python -m model_symbolic.train --epochs 5
  python -m model_symbolic.train --data dataset/processed/train_data.pt --device cuda
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, random_split

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from model_symbolic.bass_groove_model import (  # noqa: E402
    KS_IGNORE_ID,
    NOTE_OFFSET,
    PAD_ID,
    PITCH_MIN,
    REST_ID,
    BassGrooveModel,
    BassGrooveOutput,
    bar_duration_ms,
    derive_duration_ms,
    derive_keyswitch_targets,
    generate_bass_line,
)
from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("train")

BEST_CKPT = _ROOT / "checkpoints" / "best_bass_model.pt"
DEFAULT_DATA = _ROOT / "dataset" / "processed" / "train_data.pt"
CONFIG_PATH = _ROOT / "config" / "modo_bass_map.json"
OUTPUT_DIR = _ROOT / "outputs"


@dataclass
class LossWeights:
    """Sensible defaults for the multi-task bass groove objective.

    Pitch dominates token identity; keyswitch is secondary articulation accuracy;
    micro-timing / duration keep the groove human; velocity preserves dynamics.
    """

    pitch: float = 1.0
    keyswitch: float = 0.35
    micro_timing: float = 0.25
    duration: float = 0.25
    velocity: float = 0.15

    # Scale factors so Huber/MSE terms sit near CE magnitude
    micro_scale_ms: float = 50.0
    duration_scale_ms: float = 200.0
    huber_beta: float = 1.0  # SmoothL1 beta (Huber transition)


DEFAULT_LOSS_WEIGHTS = LossWeights()


class TensorGrooveDataset(Dataset):
    """Wraps list of sample dicts from train_data.pt."""

    def __init__(self, samples: List[dict]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        return self.samples[idx]


def _optional_stack(batch: List[dict], key: str, like: str = "tokens") -> torch.Tensor:
    if key in batch[0]:
        return torch.stack([b[key] for b in batch])
    ref = batch[0][like]
    return torch.zeros(len(batch), *ref.shape, dtype=torch.float32)


def collate(batch: List[dict]) -> dict:
    return {
        "tokens": torch.stack([b["tokens"] for b in batch]),
        "vels": torch.stack([b["vels"] for b in batch]),
        "micro_ms": _optional_stack(batch, "micro_ms"),
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


def compute_multitask_loss(
    out: BassGrooveOutput,
    tokens: torch.Tensor,
    vels: torch.Tensor,
    micro_ms: torch.Tensor,
    style: torch.Tensor,
    meter: torch.Tensor,
    weights: LossWeights = DEFAULT_LOSS_WEIGHTS,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """Combine pitch CE + keyswitch CE + Huber timing/duration + velocity MSE."""
    device = tokens.device
    note_mask = tokens >= NOTE_OFFSET
    _, _, vocab = out.logits.shape

    loss_pitch = F.cross_entropy(
        out.logits.reshape(-1, vocab),
        tokens.reshape(-1),
        ignore_index=PAD_ID,
    )

    ks_tgt = derive_keyswitch_targets(tokens, vels, style)
    loss_ks = F.cross_entropy(
        out.ks_logits.reshape(-1, out.ks_logits.size(-1)),
        ks_tgt.reshape(-1),
        ignore_index=KS_IGNORE_ID,
    )

    if note_mask.any():
        micro_scale = max(weights.micro_scale_ms, 1e-3)
        dur_scale = max(weights.duration_scale_ms, 1e-3)
        loss_micro = F.smooth_l1_loss(
            out.micro_ms[note_mask] / micro_scale,
            micro_ms[note_mask] / micro_scale,
            beta=weights.huber_beta,
        )
        dur_tgt = derive_duration_ms(tokens, meter)
        loss_dur = F.smooth_l1_loss(
            out.duration_ms[note_mask] / dur_scale,
            dur_tgt[note_mask] / dur_scale,
            beta=weights.huber_beta,
        )
        loss_vel = F.mse_loss(out.velocity[note_mask], vels[note_mask]) / (127.0**2)
    else:
        zero = tokens.new_zeros(())
        loss_micro = zero
        loss_dur = zero
        loss_vel = zero

    total = (
        weights.pitch * loss_pitch
        + weights.keyswitch * loss_ks
        + weights.micro_timing * loss_micro
        + weights.duration * loss_dur
        + weights.velocity * loss_vel
    )
    parts = {
        "loss": float(total.detach().item()),
        "pitch": float(loss_pitch.detach().item()),
        "keyswitch": float(loss_ks.detach().item()),
        "micro": float(loss_micro.detach().item()),
        "duration": float(loss_dur.detach().item()),
        "velocity": float(loss_vel.detach().item()),
    }
    return total, parts


@torch.no_grad()
def compute_musical_metrics(
    out: BassGrooveOutput,
    tokens: torch.Tensor,
    drum: torch.Tensor,
    chord: torch.Tensor,
) -> Dict[str, float]:
    """Akor uyum (%) and davul kick kilidi (%) on non-pad steps."""
    pred = out.logits.argmax(dim=-1)
    valid = tokens != PAD_ID
    pred_notes = pred >= NOTE_OFFSET
    sounding = valid & pred_notes

    # In-chord: predicted MIDI pitch-class active in chord chroma
    if sounding.any():
        pcs = (pred[sounding] - NOTE_OFFSET + PITCH_MIN) % 12
        chroma = chord[sounding]  # (N, 12)
        in_chord = chroma.gather(1, pcs.unsqueeze(1)).squeeze(1) > 0.5
        in_chord_pct = 100.0 * float(in_chord.float().mean().item())
    else:
        in_chord_pct = 0.0

    # Kick-lock: on kick-active steps, model should sound a note (not rest)
    kick = drum[..., 0] > 0.5
    kick_steps = valid & kick
    if kick_steps.any():
        locked = pred_notes[kick_steps]
        kick_lock_pct = 100.0 * float(locked.float().mean().item())
    else:
        # No kick annotations in batch — score agreement with target onsets as proxy
        tgt_notes = tokens >= NOTE_OFFSET
        both = valid & (pred_notes | tgt_notes)
        if both.any():
            kick_lock_pct = 100.0 * float((pred_notes == tgt_notes)[both].float().mean().item())
        else:
            kick_lock_pct = 0.0

    return {
        "in_chord_pct": in_chord_pct,
        "kick_lock_pct": kick_lock_pct,
        "n_pred_notes": int(sounding.sum().item()),
        "n_kick_steps": int(kick_steps.sum().item()),
    }


def _forward_batch(model: BassGrooveModel, batch: dict, device: str) -> Tuple[BassGrooveOutput, dict]:
    tokens = batch["tokens"].to(device)
    inp = tokens.clone()
    inp[:, 1:] = tokens[:, :-1]
    inp[:, 0] = REST_ID
    style = batch["style"].to(device)
    drum = batch["drum"].to(device)
    chord = batch["chord"].to(device)
    meter = batch["meter"].to(device)
    vels = batch["vels"].to(device)
    micro = batch["micro_ms"].to(device)
    pad_mask = tokens == PAD_ID
    out = model(inp, style, drum, chord, meter, src_key_padding_mask=pad_mask)
    moved = {
        "tokens": tokens,
        "vels": vels,
        "micro_ms": micro,
        "style": style,
        "drum": drum,
        "chord": chord,
        "meter": meter,
    }
    return out, moved


def train_epoch(
    model: BassGrooveModel,
    loader: DataLoader,
    opt: torch.optim.Optimizer,
    device: str,
    weights: LossWeights = DEFAULT_LOSS_WEIGHTS,
) -> Dict[str, float]:
    model.train()
    totals: Dict[str, float] = {
        "loss": 0.0,
        "pitch": 0.0,
        "keyswitch": 0.0,
        "micro": 0.0,
        "duration": 0.0,
        "velocity": 0.0,
    }
    n = 0
    for batch in loader:
        out, moved = _forward_batch(model, batch, device)
        loss, parts = compute_multitask_loss(
            out,
            moved["tokens"],
            moved["vels"],
            moved["micro_ms"],
            moved["style"],
            moved["meter"],
            weights=weights,
        )
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        for k, v in parts.items():
            totals[k] = totals.get(k, 0.0) + v
        n += 1
    scale = max(n, 1)
    return {k: v / scale for k, v in totals.items()}


@torch.no_grad()
def eval_epoch(
    model: BassGrooveModel,
    loader: DataLoader,
    device: str,
    weights: LossWeights = DEFAULT_LOSS_WEIGHTS,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    model.eval()
    totals: Dict[str, float] = {
        "loss": 0.0,
        "pitch": 0.0,
        "keyswitch": 0.0,
        "micro": 0.0,
        "duration": 0.0,
        "velocity": 0.0,
    }
    metric_sum = {"in_chord_pct": 0.0, "kick_lock_pct": 0.0}
    n = 0
    for batch in loader:
        out, moved = _forward_batch(model, batch, device)
        _, parts = compute_multitask_loss(
            out,
            moved["tokens"],
            moved["vels"],
            moved["micro_ms"],
            moved["style"],
            moved["meter"],
            weights=weights,
        )
        metrics = compute_musical_metrics(
            out, moved["tokens"], moved["drum"], moved["chord"]
        )
        for k, v in parts.items():
            totals[k] = totals.get(k, 0.0) + v
        metric_sum["in_chord_pct"] += metrics["in_chord_pct"]
        metric_sum["kick_lock_pct"] += metrics["kick_lock_pct"]
        n += 1
    scale = max(n, 1)
    loss_avg = {k: v / scale for k, v in totals.items()}
    metrics_avg = {k: v / scale for k, v in metric_sum.items()}
    return loss_avg, metrics_avg


def format_epoch_log(
    epoch: int,
    epochs: int,
    train_parts: Dict[str, float],
    val_parts: Optional[Dict[str, float]],
    metrics: Dict[str, float],
) -> str:
    """Single human-readable epoch line for console + Gradio Training Center."""
    base = (
        f"epoch {epoch}/{epochs}  "
        f"train_loss={train_parts['loss']:.4f} "
        f"(pitch={train_parts['pitch']:.4f} ks={train_parts['keyswitch']:.4f} "
        f"micro={train_parts['micro']:.4f} dur={train_parts['duration']:.4f} "
        f"vel={train_parts['velocity']:.4f})"
    )
    if val_parts is not None:
        base += f"  val_loss={val_parts['loss']:.4f}"
    base += (
        f"  |  Akor Uyum Oranı={metrics['in_chord_pct']:.1f}% In-Chord Notes"
        f"  |  Davul Kick Kilidi Oranı={metrics['kick_lock_pct']:.1f}% Kick-Lock Accuracy"
    )
    return base


def write_sample_midi(
    checkpoint: Path,
    out_dir: Path,
    log: Callable[[str], None] = logger.info,
) -> Path:
    """Generate a held-out-style sanity MIDI (ghost notes / groove check)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    chords = ["Am7", "D9", "Gmaj7", "Cmaj7"]
    bpm, meter = 100.0, "4/4"
    notes = generate_bass_line(
        chords,
        bpm=bpm,
        time_signature=meter,
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
    eng.write_midi(
        melody, path, play_style="Fingerstyle", bpm=bpm, time_signature=meter,
        duration_s=len(chords) * bar_duration_ms(bpm, meter) / 1000,
    )
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
    loss_weights: Optional[LossWeights] = None,
    log: Callable[[str], None] = logger.info,
) -> Path:
    weights = loss_weights or DEFAULT_LOSS_WEIGHTS
    device = resolve_device(device)
    data_path = ensure_train_data(Path(data_path), raw_dir=raw_dir, log=log)
    samples = load_train_payload(data_path)
    log(f"Loaded {len(samples)} samples from {data_path} | device={device}")
    log(
        "Multi-task loss weights: "
        + ", ".join(f"{k}={v}" for k, v in asdict(weights).items() if k in (
            "pitch", "keyswitch", "micro_timing", "duration", "velocity"
        ))
    )

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
        tr = train_epoch(model, train_loader, opt, device, weights=weights)
        if val_loader is not None:
            va, metrics = eval_epoch(model, val_loader, device, weights=weights)
            metric_loss = va["loss"]
            log(format_epoch_log(epoch, epochs, tr, va, metrics))
        else:
            # Metrics on a train pass when no val split
            _, metrics = eval_epoch(model, train_loader, device, weights=weights)
            metric_loss = tr["loss"]
            log(format_epoch_log(epoch, epochs, tr, None, metrics))
        if metric_loss < best:
            best = metric_loss
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
    parser = argparse.ArgumentParser(description="Train MODO bass groove model (multi-task)")
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
    parser.add_argument("--w-pitch", type=float, default=DEFAULT_LOSS_WEIGHTS.pitch)
    parser.add_argument("--w-keyswitch", type=float, default=DEFAULT_LOSS_WEIGHTS.keyswitch)
    parser.add_argument("--w-micro", type=float, default=DEFAULT_LOSS_WEIGHTS.micro_timing)
    parser.add_argument("--w-duration", type=float, default=DEFAULT_LOSS_WEIGHTS.duration)
    parser.add_argument("--w-velocity", type=float, default=DEFAULT_LOSS_WEIGHTS.velocity)
    args = parser.parse_args()

    import os

    raw = args.raw_dir or os.environ.get("MODO_RAW_SONGS_DIR", "")
    weights = LossWeights(
        pitch=args.w_pitch,
        keyswitch=args.w_keyswitch,
        micro_timing=args.w_micro,
        duration=args.w_duration,
        velocity=args.w_velocity,
    )
    run_training(
        data_path=Path(args.data),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device=args.device,
        out_ckpt=Path(args.out),
        raw_dir=Path(raw) if raw else None,
        loss_weights=weights,
    )


if __name__ == "__main__":
    main()
