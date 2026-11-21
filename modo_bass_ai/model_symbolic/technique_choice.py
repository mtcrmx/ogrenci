"""Learn note articulations from explicit labels and suggest playable choices."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import numpy as np
import torch
from torch import nn

from model_symbolic.note_lengths import STYLES


LABELS = (
    "normal",
    "slide_up",
    "slide_down",
    "hammer_on",
    "pull_off",
    "ghost",
    "palm_mute",
    "vibrato",
    "harmonic",
    "slap",
    "pop",
)
NODES = {
    open_pitch + offset
    for open_pitch in (28, 33, 38, 43)
    for offset in (12, 19, 24, 28, 31)
}
ALIASES = {
    "mute": "palm_mute",
    "ghost_note": "ghost",
    "harmonics": "harmonic",
    "thumb": "slap",
}


def _context(starts, lengths, pitches, velocities, phase, bpm, num, den, style):
    # Intervals and gaps use the sound of the actual receiving note. No target
    # label, mapped keyswitch or articulation-conditioned bend enters the features.
    previous = np.r_[pitches[0], pitches[:-1]]
    incoming = pitches - previous
    outgoing = np.diff(pitches, append=pitches[-1])
    prior_span = np.diff(starts, prepend=starts[0] - 2.0)
    next_span = np.diff(starts, append=starts[-1] + lengths[-1])
    previous_length = np.r_[0.0, lengths[:-1]]
    gap = np.maximum(0.0, prior_span - previous_length)
    velocity_change = np.diff(velocities, prepend=velocities[0])
    node = np.isin(pitches, list(NODES))
    features = [
        incoming / 7,
        outgoing / 7,
        abs(incoming) / 7,
        abs(outgoing) / 7,
        (pitches - 42) / 14,
        (velocities - 80) / 24,
        velocity_change / 24,
        np.log1p(4 * lengths),
        np.log1p(4 * gap),
        np.log1p(4 * prior_span),
        np.log1p(4 * next_span),
        lengths / np.maximum(next_span, 0.01),
        np.cos(2 * np.pi * phase),
        np.sin(2 * np.pi * phase),
        np.cos(2 * np.pi * starts),
        np.cos(4 * np.pi * starts),
        node.astype(float),
        np.full_like(starts, bpm / 150),
        np.full_like(starts, num / 12),
        np.full_like(starts, den / 8),
    ]
    features.extend(np.full_like(starts, float(style == s)) for s in STYLES)
    nearby = (gap <= 0.45) & (prior_span <= 2.5)
    possible = {
        "normal": np.ones(len(starts), dtype=bool),
        "slide_up": nearby & (incoming >= 1) & (incoming <= 12),
        "slide_down": nearby & (incoming <= -1) & (incoming >= -12),
        "hammer_on": nearby & (incoming >= 1) & (incoming <= 5),
        "pull_off": nearby & (incoming <= -1) & (incoming >= -5),
        "ghost": (velocities <= 76) & (lengths <= 0.6),
        "palm_mute": lengths <= 1.25,
        "vibrato": lengths * 60 / bpm >= 0.16,
        "harmonic": node & (lengths * 60 / bpm >= 0.12),
        "slap": np.full(len(starts), style == "Slap"),
        "pop": np.full(len(starts), style == "Slap"),
    }
    return np.column_stack(features).astype(np.float32), np.column_stack(
        [possible[l] for l in LABELS]
    )


def _labeled(rows):
    xs, ys, masks, families = [], [], [], []
    for row in rows:
        num, den = map(int, row["time_signature"].split("/"))
        notes = sorted(row["notes"], key=lambda n: n["beat"])
        if not notes:
            continue
        starts = np.array([n["beat"] for n in notes], dtype=float)
        phase = (starts / (num * 4 / den)) % 1
        x, m = _context(
            starts,
            np.array([n["duration"] for n in notes]),
            np.array([n["pitch"] for n in notes]),
            np.array([n["velocity"] for n in notes]),
            phase,
            row["bpm"],
            num,
            den,
            row.get("style"),
        )
        for i, note in enumerate(notes):
            tag = note.get("technique")
            tag = ALIASES.get(tag, tag)
            if tag in LABELS:
                xs.append(x[i])
                masks.append(m[i])
                ys.append(LABELS.index(tag))
                families.append(row["family"])
    if not xs:
        raise ValueError("No explicitly labelled technique events in this split")
    return (
        np.asarray(xs),
        np.asarray(ys, dtype=np.int64),
        np.asarray(masks),
        np.asarray(families),
    )


def load_technique_model(state):
    if (
        not state
        or state.get("version") != 1
        or tuple(state.get("labels", ())) != LABELS
    ):
        return None
    weights = state["weights"]
    return {
        "layers": tuple(
            (weights[f"{n}.weight"].cpu().numpy().T, weights[f"{n}.bias"].cpu().numpy())
            for n in (0, 2, 4)
        ),
        "thresholds": dict(state["thresholds"]),
        "prior_correction": np.asarray(state["prior_correction"], dtype=np.float32),
    }


def _probabilities(model, features, possible):
    x = features
    for weight, bias in model["layers"][:-1]:
        x = np.tanh(x @ weight + bias)
    weight, bias = model["layers"][-1]
    logits = x @ weight + bias - model["prior_correction"]
    logits = np.where(possible, logits, -1e6)
    exp = np.exp(logits - logits.max(axis=1, keepdims=True))
    return exp / exp.sum(axis=1, keepdims=True)


def _decisions(probs, thresholds):
    scores = np.full_like(probs, -1.0)
    scores[:, 0] = probs[:, 0]
    for j, label in enumerate(LABELS[1:], 1):
        threshold = thresholds.get(label, 1.01)
        allowed = probs[:, j] >= threshold
        scores[allowed, j] = probs[allowed, j]
    return scores.argmax(1)


def _metrics(y, predicted):
    rows = {}
    for j, label in enumerate(LABELS):
        actual = int((y == j).sum())
        emitted = int((predicted == j).sum())
        tp = int(((y == j) & (predicted == j)).sum())
        rows[label] = {
            "events": actual,
            "emitted": emitted,
            "correct": tp,
            "precision": tp / max(1, emitted),
            "recall": tp / max(1, actual),
            "f1": 2 * tp / max(1, actual + emitted),
        }
    return {
        "events": len(y),
        "accuracy": float(np.mean(y == predicted)),
        "macro_f1": float(np.mean([v["f1"] for v in rows.values() if v["events"]])),
        "classes": rows,
    }


def train_technique_model(splits, device, *, weak_rows=(), report_test=True):
    arrays = {
        s: _labeled(rows) for s, rows in splits.items() if s != "test" or report_test
    }
    train_x, y, _, group = arrays["train"]
    original_count = len(y)
    if any(n.get("technique") in LABELS for row in weak_rows for n in row["notes"]):
        wx, wy, _, wf = _labeled(weak_rows)
        train_x, y, group = (
            np.concatenate([train_x, wx]),
            np.r_[y, wy],
            np.r_[group, wf],
        )
    reliability = torch.ones(len(y), device=device)
    reliability[original_count:] = 0.35
    counts = np.bincount(y, minlength=len(LABELS))
    class_weights = (
        np.sqrt(max(counts) / np.maximum(1, counts)).clip(1, 4).astype(np.float32)
    )
    active = np.flatnonzero(counts > 0)
    correction = np.log(class_weights)
    correction[counts == 0] = 1e6
    torch.manual_seed(292)
    net = nn.Sequential(
        nn.Linear(train_x.shape[1], 64),
        nn.Tanh(),
        nn.Linear(64, 32),
        nn.Tanh(),
        nn.Linear(32, len(LABELS)),
    ).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=0.0025, weight_decay=0.006)
    vx, vy, vm, _ = arrays["validation"]
    vx_device = torch.as_tensor(vx, device=device)
    loss_weights = torch.as_tensor(class_weights, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=loss_weights, reduction="none")
    train_x = torch.as_tensor(train_x, device=device)
    targets = torch.as_tensor(y, device=device)
    best, best_epoch, weights = np.inf, 0, None
    for epoch in range(1, 141):
        for ids in torch.randperm(len(y), device=device).split(192):
            loss = (
                loss_fn(net(train_x[ids]), targets[ids]) * reliability[ids]
            ).sum() / (loss_weights[targets[ids]] * reliability[ids]).sum()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        with torch.no_grad():
            logits = net(vx_device).cpu().numpy() - correction
            # Choose the epoch by validation log loss, balanced across represented classes.
            log_prob = logits - np.logaddexp.reduce(logits, axis=1)[:, None]
            class_nll = [
                -log_prob[vy == j, j].mean() for j in active if np.any(vy == j)
            ]
            score = float(np.mean(class_nll))
        if score < best - 0.0003:
            best, best_epoch = score, epoch
            weights = {k: t.detach().cpu().clone() for k, t in net.state_dict().items()}
        if epoch - best_epoch >= 18:
            break
    blob = {
        "version": 1,
        "labels": list(LABELS),
        "weights": weights,
        "prior_correction": correction.tolist(),
        "thresholds": {},
    }
    predictor = load_technique_model(blob)
    val_probs = _probabilities(predictor, vx, vm)
    thresholds = {}
    val_argmax = val_probs.argmax(1)
    for j, label in enumerate(LABELS[1:], 1):
        positive = vy == j
        if positive.sum() < 3 or sum(y == j) < 8 or len(set(group[y == j])) < 2:
            continue
        best_score = 0.0
        for threshold in np.linspace(0.28, 0.95, 30):
            predicted = (val_probs[:, j] >= threshold) & (val_argmax == j)
            tp = (predicted & positive).sum()
            precision = tp / max(1, predicted.sum())
            recall = tp / max(1, positive.sum())
            f_score = 1.25 * precision * recall / max(1e-9, 0.25 * precision + recall)
            # Preserve ordinary playing when the selector has little evidence.
            if tp >= 2 and precision >= 0.55 and f_score > best_score:
                best_score = f_score
                thresholds[label] = round(float(threshold), 4)
    blob["thresholds"] = thresholds
    predictor = load_technique_model(blob)
    stats = {
        "selected_epoch": best_epoch,
        "thresholds": thresholds,
        "weak_training_events": len(y) - original_count,
        "training_events": int(len(y)),
        "training_counts": {LABELS[i]: int(counts[i]) for i in active},
    }
    for split in ("validation", "test") if report_test else ("validation",):
        fx, fy, mask, _ = arrays[split]
        probs = _probabilities(predictor, fx, mask)
        naive = np.full(len(fy), counts.argmax())
        stats[split] = {
            "trained": _metrics(fy, _decisions(probs, thresholds)),
            "majority": _metrics(fy, naive),
        }
    stats["enabled"] = bool(
        thresholds
        and stats["validation"]["trained"]["macro_f1"]
        > stats["validation"]["majority"]["macro_f1"]
    )
    return blob if stats["enabled"] else None, stats


def score_technique_holdout(blob, rows, majority_class):
    x, y, masks, _ = _labeled(rows)
    model = load_technique_model(blob)
    decisions = (
        _decisions(_probabilities(model, x, masks), model["thresholds"])
        if model
        else np.zeros(len(y), dtype=int)
    )
    return {
        "trained": _metrics(y, decisions),
        "majority": _metrics(y, np.full(len(y), LABELS.index(majority_class))),
    }


def suggest_techniques(
    notes,
    technique_model,
    beat_times_ms,
    duration_ms,
    bpm,
    time_signature,
    play_style,
    downbeat_times_ms=None,
    *,
    quarters_per_pulse=1.0,
):
    if not notes:
        return []
    if technique_model is None:
        return [{"normal": 1.0} for _ in notes]
    grid = np.asarray(beat_times_ms, dtype=float)
    positions = np.arange(len(grid), dtype=float) * quarters_per_pulse
    starts = np.interp([n.start_ms for n in notes], grid, positions)
    ends = np.interp([min(n.end_ms, duration_ms) for n in notes], grid, positions)
    origin = (
        np.interp(downbeat_times_ms[0], grid, positions)
        if downbeat_times_ms is not None and len(downbeat_times_ms)
        else 0.0
    )
    num, den = map(int, time_signature.split("/"))
    phase = ((starts - origin) / (num * 4 / den)) % 1
    fx, mask = _context(
        starts,
        np.maximum(0.0, ends - starts),
        np.array([n.pitch for n in notes]),
        np.array([n.velocity for n in notes]),
        phase,
        bpm,
        num,
        den,
        play_style,
    )
    probabilities = _probabilities(technique_model, fx, mask)
    allowed = {"normal", *technique_model["thresholds"]}
    suggestions = []
    for row in probabilities:
        item = {k: float(v) for k, v in zip(LABELS, row) if k in allowed and v > 0}
        item["normal"] = item.get("normal", 0.0) + max(0.0, 1.0 - sum(item.values()))
        suggestions.append(item)
    return suggestions


def apply_techniques(
    notes,
    technique_model,
    beat_times_ms,
    duration_ms,
    bpm,
    time_signature,
    play_style,
    performance_level,
    downbeat_times_ms=None,
    *,
    quarters_per_pulse=1.0,
):
    """Turn sufficiently confident suggestions into playable note articulations.

    Incoming slurs require notes reachable on the same string. Highlighted
    effects share a per-bar budget, while muted accompaniment and slap attacks
    may recur as part of the underlying playing style.
    """
    if not notes or technique_model is None:
        return notes
    proposals = suggest_techniques(
        notes,
        technique_model,
        beat_times_ms,
        duration_ms,
        bpm,
        time_signature,
        play_style,
        downbeat_times_ms,
        quarters_per_pulse=quarters_per_pulse,
    )
    num, den = map(int, time_signature.split("/"))
    beat_times = np.asarray(beat_times_ms)
    quarter_positions = np.arange(len(beat_times)) * quarters_per_pulse
    positions = np.interp([n.start_ms for n in notes], beat_times, quarter_positions)
    if downbeat_times_ms is not None and len(downbeat_times_ms):
        bars = (
            np.searchsorted(
                downbeat_times_ms, [n.start_ms + 0.25 for n in notes], side="right"
            )
            - 1
        )
    else:
        bars = np.floor(positions / (num * 4 / den)).astype(int)
    gestures = {
        "slide_up",
        "slide_down",
        "hammer_on",
        "pull_off",
        "harmonic",
        "vibrato",
    }
    transitions = {"slide_up", "slide_down", "hammer_on", "pull_off"}
    marks = ["normal"] * len(notes)
    accents = defaultdict(list)
    for i, (note, probabilities) in enumerate(zip(notes, proposals)):
        if note.velocity <= 40 or note.articulation == "ghost":
            marks[i] = "ghost"
            continue
        mark = max(probabilities, key=probabilities.get)
        confidence = probabilities[mark]
        if mark == "normal" or confidence < technique_model["thresholds"].get(
            mark, 1.01
        ):
            continue
        if mark in transitions:
            if i == 0:
                continue
            previous = notes[i - 1]
            gap_ms = note.start_ms - previous.end_ms
            if previous.velocity <= 40 or gap_ms > min(145, 60_000 / bpm * 0.25):
                continue
            if not any(
                1 <= min(note.pitch, previous.pitch) - s
                and max(note.pitch, previous.pitch) - s <= 20
                for s in (28, 33, 38, 43)
            ):
                continue
            if note.end_ms - note.start_ms < 55:
                continue
        if mark == "vibrato" and note.end_ms - note.start_ms < 285:
            continue
        if mark in gestures:
            accents[int(bars[i])].append((confidence, i, mark))
        else:
            marks[i] = mark
    budget = {"Sade": 1, "Dengeli": 2, "Hareketli": 3}[performance_level]
    for candidates in accents.values():
        selected = []
        for _, i, mark in sorted(candidates, reverse=True):
            if len(selected) >= budget:
                break
            # Neighbouring legato notes can form a phrase. Two successive
            # broad slides or vibratos need a little room to breathe.
            if mark in {"slide_up", "slide_down", "vibrato", "harmonic"} and any(
                abs(positions[i] - positions[j]) < 0.95 for j in selected
            ):
                continue
            marks[i] = mark
            selected.append(i)
    result = []
    for i, (note, mark) in enumerate(zip(notes, marks)):
        if (
            mark in transitions
            and i
            and marks[i - 1] in {"ghost", "harmonic", "palm_mute"}
        ):
            mark = "normal"
        result.append(replace(note, articulation=mark))
    return result
