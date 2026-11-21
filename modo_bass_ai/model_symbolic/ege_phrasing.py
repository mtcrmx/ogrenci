"""Shape regional bass accompaniment to leave space around the lead."""

from bisect import bisect_right
from dataclasses import replace

import numpy as np


def shape_notes(
    notes, beat_times, chords, *, downbeat_times_ms, duration_ms, level, bpm
):
    if not notes:
        return []
    changes = [
        beat_times[i] for i in range(1, len(chords)) if chords[i] != chords[i - 1]
    ]
    barlines = np.asarray(downbeat_times_ms, dtype=float)
    sizes = np.diff(np.r_[barlines, duration_ms])
    eighth = 30000 / bpm
    result = []
    for i, note in enumerate(notes):
        start = note.start_ms
        bar = bisect_right(barlines, start + 0.3) - 1
        next_attack = notes[i + 1].start_ms if i + 1 < len(notes) else duration_ms
        following_change = bisect_right(changes, start + 0.3)
        next_chord = (
            changes[following_change]
            if following_change < len(changes)
            else duration_ms
        )
        limit = min(next_chord, next_attack, duration_ms)
        available = limit - start
        if available <= 0:
            continue
        # Repeated eighths get a short breathing gap, longer pedals decay
        # naturally. The preceding note ends before harmony or silence changes.
        elapsed = (start - barlines[bar]) / max(1, sizes[bar]) if bar >= 0 else 0
        long_pedal = bar >= 0 and bar % 4 == 2 and elapsed < .10
        gate = min(available * 0.91, eighth * (2.15 if long_pedal else 1.18))
        accented = bar >= 0 and abs(start - barlines[bar]) < 18
        velocity = float(
            np.clip(0.58 * note.velocity + 0.42 * (91 if accented else 81), 63, 107)
        )
        articulation = "normal"
        if result and bar >= 0 and level != "Sade" and bar % 2 == 1:
            previous = result[-1]
            length = sizes[bar]
            position = (start - barlines[bar]) / max(1, length)
            interval = note.pitch - previous.pitch
            # An occasional soft slide leads into the end of a phrase.
            same_string = any(
                1 <= min(note.pitch, previous.pitch) - base
                and max(note.pitch, previous.pitch) - base <= 20
                for base in (28, 33, 38, 43)
            )
            if (
                0.69 <= position <= 0.93
                and 2 <= abs(interval) <= 5
                and same_string
                and 0 <= start - previous.end_ms <= 105
                and gate >= 80
                and not any(
                    n.articulation.startswith("slide") and n.start_ms >= barlines[bar]
                    for n in result[-8:]
                )
            ):
                articulation = "slide_up" if interval > 0 else "slide_down"
        result.append(
            replace(
                note,
                end_ms=start + gate,
                velocity=round(velocity),
                articulation=articulation,
            )
        )
    return result
