"""Phrase a decoded bass part against the source's measured pulse and barlines."""

from __future__ import annotations

import random
from bisect import bisect_left, bisect_right
from dataclasses import replace
from itertools import pairwise

import numpy as np

PERFORMANCE_LEVELS = ("Sade", "Dengeli", "Hareketli")


def _bar_positions(beat_times, indices, measured, pulses_per_bar):
    count = len(beat_times) - 1
    if measured is not None and len(measured):
        positions = np.interp(measured, beat_times, np.arange(count + 1))
    elif len(indices):
        positions = np.asarray(indices, dtype=float)
    else:
        positions = np.arange(0, count, pulses_per_bar)
    return np.unique(positions[(positions >= 0) & (positions < count)])


def _rhythmic_figure(slots, attacks, rng):
    """Choose a repeatable answer to the first bar's own attacks on a 16th grid."""
    # Establish a pulse before answering an attack on an eighth or a sixteenth.
    # If the model leaves a whole beat open, the answer can also land on it.
    weights = {}
    for slot in range(1, slots - 1):
        if slot not in attacks:
            pulse_strength = (5, 1, 3, 1.5)[slot % 4]
            weights[slot] = pulse_strength * (1.3 if slot - 1 in attacks else 1)
    first_half = [s for s in weights if s < slots / 2]
    second_half = [s for s in weights if s >= slots / 2]
    return [
        rng.choices(half, [weights[s] for s in half])[0]
        for half in (first_half, second_half)
        if half
    ]


def _chord_neighbor(note, chord, direction, style):
    bass, tones = chord
    reach = 12 if style == "Slap" and direction > 0 else 4
    target = int(np.clip(note.pitch + direction * reach, 29, 52))
    options = [p for p in range(28, 57) if p % 12 in (tones | {bass}) and p != note.pitch]
    return min(options, key=lambda p: abs(p - target))


def _decorate_bars(
    notes,
    beat_times,
    harmonies,
    bars,
    duration,
    quarters_per_pulse,
    style,
    active,
    groove,
    humanize_ms,
    seed,
    energy,
):
    """Keep sampled onsets, answer a figure across bars, and resolve phrase endings."""
    rng = random.Random(seed)
    original_times = [n.start_ms for n in notes]
    beat_positions = np.arange(len(beat_times))
    end_position = np.interp(duration, beat_times, beat_positions)
    bounds = [b for b in bars if b < end_position]
    if not bounds:
        return notes
    bounds.append(end_position)
    extra = []
    figures = {}
    first_chord = harmonies[int(bounds[0])]
    last_turnaround = -4
    for bar, (left, right) in enumerate(pairwise(bounds)):
        slots = round((right - left) * quarters_per_pulse * 4)
        if slots < 4:
            continue
        start, stop = np.interp([left, right], beat_positions, beat_times)
        first, after = (
            bisect_left(original_times, start - 0.01),
            bisect_left(original_times, stop - 0.01),
        )
        if after == first:
            continue
        local = original_times[first:after]
        positions = np.interp(local, beat_times, beat_positions)
        attacks = {round((p - left) * quarters_per_pulse * 4) for p in positions}
        # A native sixteenth-note performance can already occupy the rhythmic
        # space. The accompaniment's rests are as important as its attacks.
        has_space = int(slots * (0.74 if active else 0.55)) - len(local)
        budget = min(has_space, (3 if active else 1) + int(groove >= 0.7))
        local_energy = float(np.median(energy[int(left) : int(np.ceil(right))]))
        if budget <= 0 or local_energy < 0.22:
            continue
        if local_energy < 0.37:
            budget = min(budget, 1)
        if slots not in figures:
            figures[slots] = _rhythmic_figure(slots, attacks, rng)
        figure = figures[slots]
        if not figure:
            continue
        stronger_response = active and (bar % 4 in (1, 3) or local_energy > 0.72)
        selected = {figure[0]: "answer"}
        if len(figure) > 1 and (stronger_response or bar % 4 == 2):
            selected[figure[1]] = "ghost" if style in ("Slap", "Mute", "Fingerstyle") else "answer"

        upcoming = notes[after] if after < len(notes) else None
        hits_next_bar = upcoming is not None and abs(upcoming.start_ms - stop) < 10
        next_beat = min(int(right), len(harmonies) - 1)
        returns_home = harmonies[next_beat] == first_chord and harmonies[int(left)] != first_chord
        turnaround = bar % 4 == 3 or (bar > 0 and returns_home and bar - last_turnaround >= 3)
        drops = energy[next_beat] < local_energy - 0.27 or energy[next_beat] < 0.25
        if hits_next_bar and turnaround and not drops and local_energy >= 0.37:
            # Finish a four-bar thought or a return to the opening chord by
            # approaching the actual bass pitch the model plays next.
            cadence = {slots - 1: "resolve", slots - 3: "turn"}
            cadence.update((s, role) for s, role in selected.items() if s < slots - 3)
            selected = cadence
            last_turnaround = bar
        elif hits_next_bar and stronger_response and len(figure) > 1:
            # A shorter answer leaves room before the middle of a phrase.
            selected[figure[1]] = "touch" if style == "Fretless" else "ghost"

        for slot, role in selected.items():
            if budget <= 0:
                break
            pos = left + slot / (quarters_per_pulse * 4)
            beat = min(int(pos), len(harmonies) - 1)
            chord = harmonies[beat]
            if chord is None or energy[beat] < 0.22:
                continue
            at = float(np.interp(pos, beat_positions, beat_times))
            width = (beat_times[beat + 1] - beat_times[beat]) / (quarters_per_pulse * 4)
            at += rng.uniform(-1, 1) * min(width * 0.045, max(0, humanize_ms) * groove)
            at = max(beat_times[beat], at)
            index = bisect_left(original_times, at)
            if index == 0:
                continue
            previous = notes[index - 1]
            next_time = original_times[index] if index < len(notes) else duration
            if at - previous.start_ms < width * 0.7 or next_time - at < width * 0.7:
                continue
            # Leave a long played rest open. A pickup can answer the next
            # phrase near its entrance without filling the intervening silence.
            if at - previous.end_ms > 2.2 * width and next_time - at > 1.7 * width:
                continue
            clip_end = min(next_time, beat_times[beat + 1], duration, stop)
            if clip_end - at < 32:
                continue
            direction = 1 if bar % 4 < 2 else -1
            pitch = _chord_neighbor(previous, chord, direction, style)
            velocity = previous.velocity + rng.randint(-5, 3)
            articulation, passing, gate = None, False, 0.8
            if role == "ghost":
                pitch, velocity, articulation, gate = (
                    previous.pitch,
                    rng.randint(24, 37),
                    "ghost",
                    0.38,
                )
            elif role == "resolve":
                # Approach the next chord by semitone on the weakest sixteenth.
                pitch = upcoming.pitch + (1 if previous.pitch >= upcoming.pitch else -1)
                if not 28 <= pitch <= 67:
                    pitch = 2 * upcoming.pitch - pitch
                passing, gate = pitch % 12 not in chord[1], 0.96
                articulation = "legato" if abs(previous.pitch - pitch) <= 2 else None
            elif role in ("turn", "touch"):
                pitch = _chord_neighbor(previous, chord, -direction, style)
            extra.append(
                replace(
                    previous,
                    start_ms=at,
                    end_ms=min(clip_end, at + max(32, width * gate)),
                    pitch=pitch,
                    velocity=int(np.clip(velocity, 1, 122)),
                    articulation=articulation,
                    is_passing=passing,
                )
            )
            budget -= 1
    return sorted([*notes, *extra], key=lambda note: note.start_ms)


def phrase_performance(
    notes,
    beat_times,
    harmonies,
    *,
    duration_ms,
    downbeat_indices,
    downbeat_times_ms,
    quarters_per_pulse,
    pulses_per_bar,
    style,
    level,
    groove,
    humanize_ms,
    kick_ms,
    seed,
    beat_energy=None,
):
    """Phrase notes in source time, preserving the trained line's pitches and entrances."""
    if not notes:
        return notes
    energy = (
        np.full(len(harmonies), 0.5)
        if beat_energy is None
        else np.asarray(beat_energy, dtype=float)
    )
    if energy.shape != (len(harmonies),) or not np.all(np.isfinite(energy)):
        raise ValueError("Provide one finite energy value per beat.")
    energy = np.clip(energy, 0, 1)
    bars = _bar_positions(beat_times, downbeat_indices, downbeat_times_ms, pulses_per_bar)
    active = level == "Hareketli"
    notes = _decorate_bars(
        notes,
        beat_times,
        harmonies,
        bars,
        duration_ms,
        quarters_per_pulse,
        style,
        active,
        groove,
        humanize_ms,
        seed,
        energy,
    )
    kicks = sorted(kick_ms) if kick_ms is not None else []
    positions = np.interp([n.start_ms for n in notes], beat_times, np.arange(len(beat_times)))
    result = []
    for i, (note, pos) in enumerate(zip(notes, positions)):
        beat = min(int(pos), len(harmonies) - 1)
        bar = bisect_right(bars, pos + 1e-6) - 1
        downbeat = bar >= 0 and abs(pos - bars[bar]) < 0.015
        chord_entry = (beat == 0 or harmonies[beat] != harmonies[beat - 1]) and pos - beat < 0.015
        quarter = (beat_times[beat + 1] - beat_times[beat]) / quarters_per_pulse
        offbeat = abs(pos - round(pos)) > 0.08
        kick = bisect_left(kicks, note.start_ms - min(35, quarter * 0.06))
        with_kick = kick < len(kicks) and kicks[kick] <= note.start_ms + min(35, quarter * 0.06)
        accent = 10 if downbeat or chord_entry else (5 if with_kick else -7 if offbeat else 0)
        phrase_accent = (0, 2, -2, 3)[bar % 4] if bar >= 0 else -4
        intensity = (energy[beat] - 0.5) * 24
        velocity = note.velocity + (accent + phrase_accent + intensity) * (1 if active else 0.65)
        ghost = note.articulation == "ghost" or (
            note.velocity <= 40 and not (downbeat or chord_entry)
        )
        articulation = "ghost" if ghost else note.articulation
        velocity = (
            int(np.clip(round(velocity), 18, 39))
            if ghost
            else int(np.clip(round(velocity), 47, 121))
        )
        next_time = notes[i + 1].start_ms if i + 1 < len(notes) else duration_ms
        end = min(note.end_ms, next_time, duration_ms)
        # Sustain open phrases where adjacent decoded RESTs represent a held
        # note. Mute and slap keep a quicker release before the next attack.
        if ghost:
            end = min(end, note.start_ms + 0.14 * quarter)
        elif downbeat or chord_entry:
            sustain = {
                "Fretless": 1.42,
                "Fingerstyle": 1.13,
                "Pick": 0.92,
                "Slap": 0.68,
                "Mute": 0.55,
            }
            limit = beat_times[beat + 1]
            if beat + 1 < len(harmonies) and harmonies[beat + 1] == harmonies[beat]:
                limit = beat_times[beat + 2]
            gate = sustain.get(style, 1)
            end = min(
                next_time - min(12, 0.025 * quarter),
                limit,
                duration_ms,
                note.start_ms + quarter * gate,
            )
        elif style in ("Fretless", "Fingerstyle") and not note.is_passing:
            # Short decoded attacks can ring toward a following note, with a
            # deliberate release before a longer rest or a different harmony.
            breathing_room = 0.08 if style == "Fretless" else 0.20
            sustain = min((next_time - note.start_ms) * (1 - breathing_room), quarter * 0.72)
            end = min(
                max(end, note.start_ms + sustain), next_time, beat_times[beat + 1], duration_ms
            )
        if end <= note.start_ms:
            end = min(note.end_ms, next_time)
        if result and not ghost and articulation is None:
            previous = result[-1]
            interval, gap = note.pitch - previous.pitch, note.start_ms - previous.end_ms
            connected = previous.velocity > 40 and gap < 0.10 * quarter
            if (
                connected
                and 0 < abs(interval) <= 2
                and (style == "Fretless" or previous.is_passing)
            ):
                articulation = "hammer_on" if interval > 0 else "pull_off"
            elif connected and style == "Fretless" and 3 <= abs(interval) <= 7 and downbeat:
                articulation = "slide"
        result.append(replace(note, end_ms=end, velocity=velocity, articulation=articulation))
    return result
