"""Learn and apply note releases in quarter-note time, after choosing all attacks."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import torch
from torch import nn

STYLES = ("Fingerstyle", "Pick", "Slap", "Fretless", "Mute")


def _features(starts, spans, pitches, velocities, phase, bpm, num, den, style):
    intervals = np.diff(starts, prepend=starts[0] - 1)
    columns = [
        np.log1p(4 * spans),
        np.log1p(4 * intervals),
        (pitches - 42) / 12,
        (velocities - 80) / 32,
        np.diff(pitches, append=pitches[-1]) / 12,
        np.diff(pitches, prepend=pitches[0]) / 12,
        np.sin(2 * np.pi * phase),
        np.cos(2 * np.pi * phase),
        np.cos(2 * np.pi * starts),
        np.cos(4 * np.pi * starts),
        np.full_like(starts, bpm / 150),
        np.full_like(starts, num / 12),
        np.full_like(starts, den / 8),
    ]
    columns.extend(np.full_like(starts, float(style == s)) for s in STYLES)
    return np.column_stack(columns).astype(np.float32)


def _spans(starts, end, changes):
    next_attacks = np.r_[starts[1:], end]
    boundaries = np.r_[changes, end]
    next_change = boundaries[
        np.minimum(
            np.searchsorted(boundaries, starts + 1e-8, side="right"),
            len(boundaries) - 1,
        )
    ]
    return np.minimum(
        np.maximum(0.0, np.minimum(next_attacks, next_change) - starts), 4.0
    )


def _examples(rows):
    features, limits, targets, fixed, bpms = [], [], [], [], []
    for row in rows:
        num, den = map(int, row["time_signature"].split("/"))
        width = num * 4 / den
        end = row["bars"] * width
        notes = sorted(
            (
                n
                for n in row["notes"]
                if 0 <= n["beat"] < end and 28 <= n["pitch"] <= 67
            ),
            key=lambda n: n["beat"],
        )
        if not notes:
            continue
        starts = np.array([n["beat"] for n in notes], dtype=float)
        pitches = np.array([n["pitch"] for n in notes])
        velocities = np.array([n["velocity"] for n in notes])
        changes = [
            i * width
            for i in range(1, len(row["chords"]))
            if row["chords"][i] != row["chords"][i - 1]
        ]
        if row.get("chord_changes"):
            changes = sorted({float(c["beat"]) for c in row["chord_changes"] if 0 < float(c["beat"]) < end})
        space = _spans(starts, end, changes)
        durations = np.minimum([n["duration"] for n in notes], space)
        style = row.get("style")
        valid = (durations > 0.01) & (space > 0.02)
        if not valid.any():
            continue
        # Reference release used by the native grid decoder before ornaments.
        phase_in_quarter = np.rint(starts * 4).astype(int) % 4
        gate = 0.65 if style in ("Mute", "Slap") else 0.93
        fixed_gate = np.minimum(
            space, np.where(phase_in_quarter == 0, 1.0, 0.25) * gate
        )
        features.append(
            _features(
                starts,
                space,
                pitches,
                velocities,
                (starts % width) / width,
                row["bpm"],
                num,
                den,
                style,
            )[valid]
        )
        limits.extend(space[valid])
        targets.extend(durations[valid])
        fixed.extend(fixed_gate[valid])
        bpms.extend([row["bpm"]] * int(valid.sum()))
    return (
        np.concatenate(features),
        *(np.asarray(col, dtype=np.float32) for col in (limits, targets, fixed, bpms)),
    )


def _metric(predict, expected, bpms):
    error = np.abs(predict - expected)
    return {
        "mae_quarters": float(error.mean()),
        "mae_ms": float((error * 60000 / bpms).mean()),
        "events": len(error),
    }


def train_duration_model(splits, device):
    """Select by validation MAE, then measure the untouched test families once."""
    arrays = {k: _examples(v) for k, v in splits.items()}
    torch.manual_seed(5102)
    x, space, target, _, _ = arrays["train"]
    ratio = target / np.maximum(0.01, space)
    order = np.argsort(ratio)
    # Strong constant reference: training-set MAE optimum weighted by time.
    median_gate = float(
        ratio[order[np.searchsorted(np.cumsum(space[order]), space.sum() / 2)]]
    )
    x, space, target = (torch.as_tensor(a, device=device) for a in (x, space, target))
    net = nn.Sequential(
        nn.Linear(x.shape[1], 48),
        nn.Tanh(),
        nn.Linear(48, 24),
        nn.Tanh(),
        nn.Linear(24, 1),
        nn.Sigmoid(),
    ).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=0.003, weight_decay=0.003)
    vx, vs, vy, _, _ = arrays["validation"]
    vx, vs, vy = (torch.as_tensor(a, device=device) for a in (vx, vs, vy))
    best, best_epoch, state = np.inf, 0, None
    for epoch in range(1, 81):
        for ids in torch.randperm(len(x), device=device).split(512):
            pred = net(x[ids]).squeeze(-1) * space[ids]
            loss = torch.nn.functional.smooth_l1_loss(pred, target[ids], beta=0.035)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        with torch.no_grad():
            metric = (net(vx).squeeze(-1) * vs - vy).abs().mean().item()
        if metric < best:
            best, best_epoch = metric, epoch
            state = {k: t.detach().cpu().clone() for k, t in net.state_dict().items()}
        if epoch - best_epoch >= 12:
            break
    blob = {"version": 1, "weights": state}
    layers = load_duration_model(blob)
    stats = {"selected_epoch": best_epoch, "constant_gate": median_gate}
    for split in ("validation", "test"):
        x, space, expected, fixed, bpms = arrays[split]
        predicted = space * _predict(layers, x)
        stats[split] = {
            "learned": _metric(predicted, expected, bpms),
            "native_fixed": _metric(fixed, expected, bpms),
            "trained_constant": _metric(median_gate * space, expected, bpms),
        }
    val = stats["validation"]
    enabled = val["learned"]["mae_quarters"] < min(
        val[name]["mae_quarters"] for name in ("native_fixed", "trained_constant")
    )
    stats["enabled"] = enabled
    return blob if enabled else None, stats


def load_duration_model(state):
    if not state or state.get("version") != 1:
        return None
    weights = state["weights"]
    return tuple(
        (
            weights[f"{n}.weight"].detach().cpu().numpy().T,
            weights[f"{n}.bias"].detach().cpu().numpy(),
        )
        for n in (0, 2, 4)
    )


def _predict(layers, x):
    for weight, bias in layers[:-1]:
        x = np.tanh(x @ weight + bias)
    weight, bias = layers[-1]
    return (1 / (1 + np.exp(-np.clip(x @ weight + bias, -25, 25)))).ravel()


def apply_note_lengths(
    notes,
    duration_model,
    beat_times_ms,
    beat_chords,
    duration_ms,
    bpm,
    time_signature,
    play_style,
    downbeat_times_ms=None,
    *,
    quarters_per_pulse=1.0,
):
    """Keep attack times; map learned quarter lengths back through the local tempo map."""
    if not notes or duration_model is None:
        return notes
    beats = np.asarray(beat_times_ms, dtype=float)
    coordinates = np.arange(len(beats)) * quarters_per_pulse
    starts_ms = np.array([n.start_ms for n in notes])
    starts = np.interp(starts_ms, beats, coordinates)
    end = np.interp(duration_ms, beats, coordinates)
    changes = [
        coordinates[i]
        for i in range(1, len(beat_chords))
        if beat_chords[i] != beat_chords[i - 1]
    ]
    changes = [c for c in changes if c < end]
    space = _spans(starts, end, changes)
    num, den = map(int, time_signature.split("/"))
    width = num * 4 / den
    origin = 0.0
    if downbeat_times_ms is not None and len(downbeat_times_ms):
        origin = np.interp(downbeat_times_ms[0], beats, coordinates)
    features = _features(
        starts,
        space,
        np.array([n.pitch for n in notes]),
        np.array([n.velocity for n in notes]),
        ((starts - origin) % width) / width,
        bpm,
        num,
        den,
        play_style,
    )
    lengths = _predict(duration_model, features) * space
    ends_ms = np.interp(starts + lengths, coordinates, beats)
    result = []
    for idx, (note, learned_end) in enumerate(zip(notes, ends_ms)):
        cap = min(
            duration_ms,
            starts_ms[idx + 1] if idx + 1 < len(starts_ms) else duration_ms,
            np.interp(starts[idx] + space[idx], coordinates, beats),
        )
        if note.articulation in {"ghost", "mute", "palm_mute"} or note.velocity <= 40:
            cap = min(cap, note.end_ms)
        result.append(
            replace(note, end_ms=float(min(cap, max(note.start_ms + 1, learned_end))))
        )
    return result
