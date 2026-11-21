"""Train BassGrooveModel on synthetic rule-generated sequences (bootstrapping).

Usage (from project root or via -m):
  python -m model_symbolic.train --epochs 5 --out checkpoints/bass_groove.pt
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import sys
from pathlib import Path
from typing import List, Tuple

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

# Allow running as script from project root
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from model_symbolic.bass_groove_model import (  # noqa: E402
    NOTE_OFFSET,
    PAD_ID,
    PITCH_MIN,
    REST_ID,
    STYLE_TO_ID,
    BassGrooveModel,
    beat_duration_ms,
    generate_bass_line_rules,
    parse_chord,
    parse_time_signature,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("train")

SYNTH_PROGRESSIONS = [
    "Am7 | D9 | Gmaj7 | Cmaj7",
    "Cm7 | F7 | Bbmaj7 | Ebmaj7",
    "Em7 | A7 | Dmaj7 | Gmaj7",
    "Dm7 | G7 | Cmaj7 | Fmaj7",
    "Am | F | C | G",
    "Em | C | G | D",
    "F#m7 | B7 | Emaj7 | Amaj7",
    "Gm7 | C7 | Fmaj7 | Bbmaj7",
]
METERS = ["4/4", "3/4", "7/8", "9/8", "5/8", "6/8"]
STYLES = list(STYLE_TO_ID.keys())


class SyntheticGrooveDataset(Dataset):
    def __init__(self, n_samples: int = 256, max_steps: int = 128, seed: int = 0) -> None:
        self.n_samples = n_samples
        self.max_steps = max_steps
        self.rng = random.Random(seed)
        self.cache: List[dict] = [self._make_one(i) for i in range(n_samples)]

    def _make_one(self, idx: int) -> dict:
        rng = random.Random(self.rng.randint(0, 10_000_000) + idx)
        prog = rng.choice(SYNTH_PROGRESSIONS)
        chords = [c.strip() for c in prog.split("|")]
        bpm = rng.uniform(70, 140)
        ts = rng.choice(METERS)
        style = rng.choice(STYLES)
        groove = rng.uniform(0.2, 0.9)
        human = rng.uniform(4, 18)
        num, den = parse_time_signature(ts)
        beat_ms = beat_duration_ms(bpm, den)
        bar_ms = beat_ms * num
        total_ms = bar_ms * len(chords)

        # Fake kick/snare on beats
        kick = [b * beat_ms for b in range(0, int(total_ms / beat_ms), num)]
        snare = []
        if den == 4 and num >= 4:
            for bar in range(len(chords)):
                snare.append(bar * bar_ms + 2 * beat_ms)

        notes = generate_bass_line_rules(
            chords,
            bpm,
            ts,
            style,
            kick_ms=kick,
            snare_ms=snare,
            humanize_ms=human,
            groove_amount=groove,
            seed=rng.randint(0, 99999),
        )

        step = beat_ms / 2
        n_steps = min(self.max_steps, max(8, int(math.ceil(total_ms / step))))
        tokens = [REST_ID] * n_steps
        vels = [0.0] * n_steps
        for n in notes:
            i = int(round(n.start_ms / step))
            if 0 <= i < n_steps:
                tokens[i] = int(n.pitch - PITCH_MIN + NOTE_OFFSET)
                vels[i] = float(n.velocity)

        drum = torch.zeros(n_steps, 2)
        chord_f = torch.zeros(n_steps, 12)
        meter = torch.zeros(n_steps, 4)
        for i in range(n_steps):
            t_ms = i * step
            bar_i = min(len(chords) - 1, int(t_ms // bar_ms))
            root, tones = parse_chord(chords[bar_i])
            for tt in tones:
                chord_f[i, (root + tt) % 12] = 1.0
            beat_idx = int(round(t_ms / beat_ms))
            if any(abs(t_ms - k) < step for k in kick):
                drum[i, 0] = 1.0
            if any(abs(t_ms - s) < step for s in snare):
                drum[i, 1] = 1.0
            meter[i] = torch.tensor(
                [num / 16.0, den / 16.0, min(bpm, 240) / 240.0, (t_ms % bar_ms) / bar_ms]
            )

        # Pad to max_steps
        pad_n = self.max_steps - n_steps
        if pad_n > 0:
            tokens = tokens + [PAD_ID] * pad_n
            vels = vels + [0.0] * pad_n
            drum = torch.cat([drum, torch.zeros(pad_n, 2)], dim=0)
            chord_f = torch.cat([chord_f, torch.zeros(pad_n, 12)], dim=0)
            meter = torch.cat([meter, torch.zeros(pad_n, 4)], dim=0)
            length = n_steps
        else:
            tokens = tokens[: self.max_steps]
            vels = vels[: self.max_steps]
            length = self.max_steps

        return {
            "tokens": torch.tensor(tokens, dtype=torch.long),
            "vels": torch.tensor(vels, dtype=torch.float32),
            "drum": drum,
            "chord": chord_f,
            "meter": meter,
            "style": torch.tensor(STYLE_TO_ID[style], dtype=torch.long),
            "length": length,
        }

    def __len__(self) -> int:
        return self.n_samples

    def __getitem__(self, idx: int) -> dict:
        return self.cache[idx]


def collate(batch: List[dict]) -> dict:
    return {
        "tokens": torch.stack([b["tokens"] for b in batch]),
        "vels": torch.stack([b["vels"] for b in batch]),
        "drum": torch.stack([b["drum"] for b in batch]),
        "chord": torch.stack([b["chord"] for b in batch]),
        "meter": torch.stack([b["meter"] for b in batch]),
        "style": torch.stack([b["style"] for b in batch]),
        "length": torch.tensor([b["length"] for b in batch]),
    }


def train_epoch(model: BassGrooveModel, loader: DataLoader, opt: torch.optim.Optimizer, device: str) -> float:
    model.train()
    total = 0.0
    n = 0
    for batch in loader:
        tokens = batch["tokens"].to(device)
        # Teacher forcing: input is shifted right
        inp = tokens.clone()
        inp[:, 1:] = tokens[:, :-1]
        inp[:, 0] = REST_ID
        style = batch["style"].to(device)
        drum = batch["drum"].to(device)
        chord = batch["chord"].to(device)
        meter = batch["meter"].to(device)
        lengths = batch["length"]
        # Padding mask: True where pad
        pad_mask = tokens == PAD_ID

        logits, vel_pred = model(inp, style, drum, chord, meter, src_key_padding_mask=pad_mask)
        # Loss only on non-pad positions
        B, T, V = logits.shape
        loss_ce = F.cross_entropy(logits.reshape(-1, V), tokens.reshape(-1), ignore_index=PAD_ID)
        # Velocity where note tokens
        note_mask = tokens >= NOTE_OFFSET
        if note_mask.any():
            loss_vel = F.mse_loss(vel_pred[note_mask], batch["vels"].to(device)[note_mask]) / (127.0**2)
        else:
            loss_vel = torch.tensor(0.0, device=device)
        loss = loss_ce + 0.1 * loss_vel
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        total += float(loss.item())
        n += 1
        _ = lengths
    return total / max(n, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MODO bass groove Transformer")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--out", type=str, default=str(_ROOT / "checkpoints" / "bass_groove.pt"))
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    device = args.device
    ds = SyntheticGrooveDataset(n_samples=args.samples)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    model = BassGrooveModel().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    for epoch in range(1, args.epochs + 1):
        loss = train_epoch(model, loader, opt, device)
        logger.info("epoch %d/%d  loss=%.4f", epoch, args.epochs, loss)

    out = Path(args.out)
    model.save(out)
    logger.info("saved %s", out)


if __name__ == "__main__":
    main()
