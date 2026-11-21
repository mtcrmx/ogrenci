"""Velocity calibration for backing-track accompaniment, fitted to acoustic note labels."""

import argparse
import json
import math
from itertools import chain
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr


def _features(raw, pitch, quarter_phase):
    # Normalize on this recording only. Inference uses the generated raw
    # velocities, never the source bass or its energy distribution.
    raw = np.asarray(raw, dtype=float)
    pitch = np.asarray(pitch, dtype=float)
    phase = np.asarray(quarter_phase, dtype=float)
    subdivision = np.rint(4 * phase).astype(int)
    return np.column_stack(
        (
            raw - np.median(raw),
            pitch - np.median(pitch),
            (subdivision % 4 == 0).astype(float),
            (subdivision == 0).astype(float),
        )
    )


def calibrated_velocities(params, raw, pitch, quarter_phase):
    """Return unrounded velocities using generated notes from one recording."""
    features = _features(raw, pitch, quarter_phase)
    value = float(params["center"]) + features @ np.asarray(params["coefficients"])
    return np.clip(value, 1.0, 127.0)


def recording_velocity_prediction(hidden, original_velocity, calibration):
    """Optional small acoustic readout of the already computed context."""
    if not calibration or "readout" not in calibration:
        return original_velocity
    coefficients = hidden.new_tensor(calibration["readout"])
    if coefficients.shape != (hidden.shape[-1],):
        raise ValueError("Invalid recording velocity readout dimensions")
    return (hidden @ coefficients + calibration["bias"]).clamp(1, 127)


def velocity_observations(model, rows):
    """Extract teacher-forced per-attack input/target pairs at the native grid."""
    import torch

    from model_symbolic.bass_groove_model import NOTE_OFFSET, PITCH_MIN
    from model_symbolic.train_performance import pack, predict, transform

    groups = {}
    model.eval()
    device = next(model.parameters()).device
    with torch.inference_mode():
        for family in sorted({r["family"] for r in rows}):
            group = [r for r in rows if r["family"] == family]
            data, _ = pack(group, device)
            chunks = []
            for ids in torch.arange(len(data["tokens"]), device=device).split(48):
                batch = transform(data, ids, False)
                good = batch["tokens"] >= NOTE_OFFSET
                hidden = []
                with model.vel_head.register_forward_pre_hook(
                    lambda module, args, selected=good, captured=hidden: (
                        captured.append(args[0][selected].T)
                    )
                ):
                    raw = predict(model, batch)[1][good]
                meter = batch["meter"][good]
                width = 4 * meter[:, 0] / meter[:, 1]
                values = torch.stack(
                    (
                        raw,
                        batch["tokens"][good] - NOTE_OFFSET + PITCH_MIN,
                        meter[:, 3] * width,
                        batch["velocity"][good],
                    )
                )
                chunks.append(torch.cat([values, hidden[0]]).cpu().numpy())
            groups[family] = np.concatenate(chunks, axis=1)
    return groups


def _metrics(target, velocity):
    corr = (
        float(spearmanr(target, velocity).statistic)
        if np.ptp(velocity) and np.ptp(target)
        else 0.0
    )
    return {
        "notes": len(target),
        "mae": float(np.mean(np.abs(target - velocity))),
        "target_mean": float(np.mean(target)),
        "prediction_mean": float(np.mean(velocity)),
        "target_sd": float(np.std(target)),
        "prediction_sd": float(np.std(velocity)),
        "target_p90_minus_p10": float(np.diff(np.quantile(target, [0.1, 0.9]))[0]),
        "prediction_p90_minus_p10": float(
            np.diff(np.quantile(velocity, [0.1, 0.9]))[0]
        ),
        "spearman": corr,
    }


def recording_scores(observations, calibration=None):
    result = {}
    outputs, targets = [], []
    for name, observation in observations.items():
        raw, pitch, phase, target = observation[:4]
        if calibration and "readout" in calibration:
            predicted = np.clip(
                np.asarray(calibration["readout"]) @ observation[4:]
                + calibration["bias"],
                1,
                127,
            )
        elif calibration:
            predicted = calibrated_velocities(calibration, raw, pitch, phase)
        else:
            predicted = raw
        result[name] = _metrics(target, predicted)
        outputs.append(predicted)
        targets.append(target)
    result["pooled"] = _metrics(np.concatenate(targets), np.concatenate(outputs))
    return result


def _candidates(groups):
    # Square-root song weights retain more information from long performances
    # without letting the two long multitracks dominate the entire population.
    fx, labels, weights, ratios = [], [], [], []
    for observation in groups.values():
        raw, pitch, phase, target = observation[:4]
        fx.append(_features(raw, pitch, phase))
        labels.append(target)
        weights.append(np.full(len(raw), 1 / math.sqrt(len(raw))))
        ratios.append(np.std(target) / max(0.5, np.std(raw)))
    x = np.concatenate(fx)
    y = np.concatenate(labels)
    weight = np.concatenate(weights)
    weight /= np.sum(weight)
    ratio = float(np.clip(np.median(ratios), 0.70, 1.65))
    for slope in sorted({1.0, ratio}):
        for contextual in (False, True):
            coeffs = np.array([slope, 0.0, 0.0, 0.0])
            if contextual:
                features = x[:, 1:]
                mean = np.average(features, axis=0, weights=weight)
                normalized = features - mean
                residual = y - slope * x[:, 0]
                # Shared ridge fit for register and beat accents only. Bound
                # per-semitone and metrical effects in MIDI velocity units.
                penalty = np.diag([5.0, 0.15, 0.15])
                coeffs[1:] = np.clip(
                    np.linalg.solve(
                        normalized.T @ (normalized * weight[:, None]) + penalty,
                        normalized.T @ (weight * residual),
                    ),
                    [-0.40, -4, -4],
                    [0.40, 4, 4],
                )
            intercept = float(np.average(y - x @ coeffs, weights=weight))
            name = ("contrast_matched" if slope != 1 else "center_only") + (
                "_context" if contextual else ""
            )
            yield (
                name,
                {"version": 1, "center": intercept, "coefficients": coeffs.tolist()},
            )


def _readout_candidates(train, teacher):
    # The small linear readout is learned independently of the MIDI velocity
    # output. Distilling the previous acoustic output is one optional target.
    # Both teachers and measured targets here come only from training songs.
    x = np.concatenate([a[4:].T for a in train.values()]).astype(float)
    acoustic = np.concatenate([a[3] for a in train.values()])
    old = np.concatenate([teacher[key][0] for key in train])
    native_contour = np.concatenate([a[0] - np.median(a[0]) for a in train.values()])
    weights = np.concatenate(
        [np.full(a.shape[1], 1 / math.sqrt(a.shape[1])) for a in train.values()]
    )
    weights /= weights.sum()
    center = np.average(x, weights=weights, axis=0)
    centered = x - center
    cov = centered.T @ (weights[:, None] * centered)
    for teacher_weight, native_prior in (
        (0.0, 0.0),
        (0.5, 0.0),
        (0.5, 0.45),
        (1.0, 0.45),
    ):
        y = (
            (1 - teacher_weight) * acoustic
            + teacher_weight * old
            + native_prior * native_contour
        )
        target_center = np.average(y, weights=weights)
        rhs = centered.T @ (weights * (y - target_center))
        for penalty in (0.02, 0.20):
            coeff = np.linalg.solve(cov + np.eye(len(center)) * penalty, rhs)
            fitted = centered @ coeff
            gain = np.clip(
                np.sqrt(
                    np.average(
                        (acoustic - np.average(acoustic, weights=weights)) ** 2,
                        weights=weights,
                    )
                    / max(0.01, np.average(fitted**2, weights=weights))
                ),
                1,
                1.65,
            )
            for k in sorted({1.0, float(gain)}):
                w = coeff * k
                name = f"readout_teacher{teacher_weight:.1f}_prior{native_prior:.2f}_ridge{penalty:.2f}_gain{k:.2f}"
                yield (
                    name,
                    {
                        "version": 1,
                        "readout": w.tolist(),
                        "bias": float(target_center - center @ w),
                    },
                )


def fit_recording_calibration(model, previous, train_rows, validation_rows):
    """Select using held-out studio recordings. No test rows are accepted."""
    if any(r["split"] != "train" for r in train_rows) or any(
        r["split"] != "validation" for r in validation_rows
    ):
        raise ValueError(
            "Calibration requires explicit training and validation splits."
        )
    train = velocity_observations(model, train_rows)
    valid = velocity_observations(model, validation_rows)
    if train.keys() & valid.keys():
        raise ValueError("Recording calibration requires song-disjoint validation.")
    baseline = recording_scores(valid)
    old = recording_scores(velocity_observations(previous, validation_rows))
    report = {
        "training_songs": {k: int(v.shape[1]) for k, v in train.items()},
        "raw_validation": baseline,
        "previous_acoustic_validation": old,
        "candidates": {},
    }
    chosen = None
    chosen_name = "raw"
    best = float("inf")
    train_teacher = velocity_observations(previous, train_rows)
    for name, params in chain(
        _candidates(train), _readout_candidates(train, train_teacher)
    ):
        stats = recording_scores(valid, params)
        # Keep contrast and rank in every song. Optimize the remaining
        # candidates with equal weights per validation song.
        passed = True
        scores = []
        for song in valid:
            s, raw = stats[song], baseline[song]
            ratio = s["prediction_sd"] / max(0.25, s["target_sd"])
            passed &= s["mae"] < raw["mae"] and 0.40 <= ratio <= 2.5
            passed &= s["spearman"] >= raw["spearman"] - 0.06
            scores.append(
                s["mae"] / max(1, s["target_sd"])
                + 0.35 * abs(math.log(max(0.01, ratio)))
                - 0.25 * s["spearman"]
            )
        objective = float(np.mean(scores))
        report["candidates"][name] = {
            "eligible": bool(passed),
            "validation": stats,
            "score": objective,
        }
        if passed and objective < best:
            chosen, chosen_name, best = params, name, objective
    # Re-centering after a complete piece is an offline comparator. Deploy
    # only an online context readout that also beats that validation baseline.
    if chosen and "readout" not in chosen:
        chosen, chosen_name = None, "raw"
    report["selected"] = chosen_name
    report["selected_validation"] = recording_scores(valid, chosen)
    return chosen, report


def main():
    from model_symbolic.bass_groove_model import load_model_from_checkpoint
    from model_symbolic.train_performance import DATA, ROOT, json_rows, split_families

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint", type=Path, default=ROOT / "checkpoints/ensemble_bass.pt"
    )
    parser.add_argument(
        "--baseline", type=Path, default=ROOT / "checkpoints/session_bass.pt"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    songs = split_families(json_rows(DATA / "song_performances.jsonl"))
    params, report = fit_recording_calibration(
        load_model_from_checkpoint(args.checkpoint),
        load_model_from_checkpoint(args.baseline),
        songs["train"],
        songs["validation"],
    )
    report["parameters"] = params
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report["selected"], report["selected_validation"]["pooled"])


if __name__ == "__main__":
    main()
