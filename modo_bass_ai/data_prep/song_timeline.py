"""Estimate a performance timeline directly from an uploaded local audio file.

Times are seconds from the original file start. Beat positions are quarter
notes; a bar occupies numerator * 4 / denominator quarters. Integer downbeat
indices are a convenience: bar_starts_s also represents half-quarter boundaries.
Chord and meter estimates are hypotheses, not ground-truth transcriptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from scipy import fft, ndimage, signal

from data_prep.chordino import fill_sparse_chords


_SR = 11025
_HOP = 128
_CHROMA_HOP = 512
_NAMES = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
_TRIADS = np.zeros((24, 12))
for _index in range(24):
    _root = _index % 12
    _third = 3 if _index >= 12 else 4
    _TRIADS[_index, [_root, (_root + _third) % 12, (_root + 7) % 12]] = [1, 0.90, 0.85]
_TRIADS /= np.linalg.norm(_TRIADS, axis=1, keepdims=True)


@dataclass
class SongTimeline:
    duration_s: float
    bpm: float
    time_signature: str
    music_start_s: float
    beat_times_s: list[float]
    downbeat_s: float
    downbeat_indices: list[int]
    bar_starts_s: list[float]
    bar_ends_s: list[float]
    chords: list[str]
    beat_chords: list[str]
    key: str
    harmonic_confidence: float
    beat_confidence: float
    meter_confidence: float
    warnings: list[str]
    kick_ms: list[float]
    snare_ms: list[float]
    beat_energy: list[float] | None = None

    @property
    def start_s(self) -> float:
        return self.beat_times_s[0]


def _spectra(y, size, hop):
    """Yield centered spectra in bounded blocks, including the first frame."""
    padded = np.pad(y, size // 2)
    windows = np.lib.stride_tricks.sliding_window_view(padded, size)[::hop]
    window = signal.windows.hann(size, sym=False).astype(np.float32)
    for start in range(0, len(windows), 384):
        yield np.abs(fft.rfft(windows[start : start + 384] * window, axis=-1))


def _rhythm(y):
    # A parallel low-frequency envelope helps place downbeats in a busy mix.
    mel = librosa.filters.mel(sr=_SR, n_fft=512, n_mels=40, fmin=35, fmax=5000)
    bands = []
    for magnitude in _spectra(y, 512, _HOP):
        bands.append(np.log1p(100 * (magnitude @ mel.T)))
    band = np.concatenate(bands)
    change = np.maximum(0, np.diff(band, axis=0, prepend=band[:1]))
    return change.mean(axis=1), change[:, :6].mean(axis=1)


def _drum_cues(y, onset):
    """Transient candidates from a mix; never claim an isolated drum stem."""
    peaks, _ = signal.find_peaks(
        onset, distance=6, prominence=max(0.002, np.percentile(onset, 95) * 0.20)
    )
    size = 512
    hz = fft.rfftfreq(size, 1 / _SR)
    window = signal.windows.hann(size, sym=False)
    kicks, snares = [], []
    for peak in peaks:
        pos = int(peak * _HOP)
        attack = y[max(0, pos - 64) : pos - 64 + size]
        if len(attack) != size:
            continue
        power = np.abs(fft.rfft(attack * window)) ** 2
        total = max(1e-10, power.sum())
        low = power[(hz >= 36) & (hz < 190)].sum() / total
        high = power[hz >= 1500].sum() / total
        flatness = np.exp(np.mean(np.log(power[2:] + 1e-12))) / (power[2:].mean() + 1e-12)
        time_ms = float((peak + 1) * _HOP * 1000 / _SR)
        if high > 0.19 and flatness > 0.035:
            snares.append(time_ms)
        elif low > 0.40 and (high > 0.014 or flatness > 0.007):
            kicks.append(time_ms)
    return kicks, snares


def _harmony(y):
    """Peak-interpolated pitch classes, with weaker votes for likely overtones."""
    size = 4096
    chroma_blocks, bass_blocks, fundamental_blocks, tuning_blocks, balanced_blocks = [], [], [], [], []
    for mag in _spectra(y, size, _CHROMA_HOP):
        center = mag[:, 1:-1]
        peaks = (center > mag[:, :-2]) & (center >= mag[:, 2:])
        peaks &= center > np.maximum(mag.max(axis=1, keepdims=True) * 0.047, 0.0001)
        frames, bins = np.nonzero(peaks)
        bins += 1
        usable = (bins >= 11) & (bins <= 1200)
        frames, bins = frames[usable], bins[usable]
        amp = mag[frames, bins]
        left = np.log(np.maximum(mag[frames, bins - 1], 1e-9))
        mid = np.log(np.maximum(amp, 1e-9))
        right = np.log(np.maximum(mag[frames, bins + 1], 1e-9))
        shift = 0.5 * (left - right) / np.minimum(left - 2 * mid + right, -1e-6)
        hz = (bins + np.clip(shift, -0.5, 0.5)) * _SR / size
        midi = 69 + 12 * np.log2(hz / 440)
        quantized = np.rint(midi).astype(int)
        pitch_class = quantized % 12
        note_weight = np.exp(-0.5 * ((midi - quantized) / 0.32) ** 2)
        # Fundamental peaks are generally narrower and taller than noise peaks.
        total_power = np.sum(mag * mag, axis=1)
        peak_ratio = amp * amp / np.maximum(total_power[frames], 1e-12)
        weight = amp * note_weight * np.clip(peak_ratio / 0.035, 0, 1)
        sub = np.maximum(
            mag[frames, np.rint(bins / 2).astype(int)], mag[frames, np.rint(bins / 3).astype(int)]
        )
        weight /= 1 + np.minimum(2, sub / np.maximum(amp, 1e-9))
        shape = (len(mag), 12)
        chroma, bass = np.zeros(shape), np.zeros(shape)
        np.add.at(chroma, (frames, pitch_class), weight)
        # A full mix may put nearly all its peak energy into the existing
        # bass line. Give accompaniment in higher registers a bounded vote.
        register = np.digitize(hz, (150.0, 450.0))
        register_level = np.zeros((len(mag), 3))
        np.add.at(register_level, (frames, register), weight)
        total = register_level.sum(axis=1)
        equalized = weight / np.maximum(register_level[frames, register] + 0.04 * total[frames], 1e-9) ** 0.75
        balanced = np.zeros(shape)
        np.add.at(balanced, (frames, pitch_class), equalized)
        low = hz <= 210
        np.add.at(bass, (frames[low], pitch_class[low]), weight[low])
        # A distorted string can produce a very convincing major triad from
        # partials 3 and 5 alone. Keep separate evidence from peaks with no
        # plausible lower fundamental; a true guitar fifth is only 1.5x its root.
        lower = np.zeros_like(amp)
        peak_hz = np.zeros_like(mag)
        peak_hz[frames, bins] = hz
        for partial in range(2, 10):
            target = hz / partial
            nearest = np.rint(target * size / _SR).astype(int)
            for offset in (-1, 0, 1):
                idx = np.maximum(0, nearest + offset)
                # A loud neighboring note or drum energy at this frequency is
                # insufficient. Its own interpolated peak must fit the ratio.
                aligned = np.abs(peak_hz[frames, idx] - target) < target * 0.018
                lower = np.maximum(lower, np.where(aligned, mag[frames, idx], 0))
        independent = amp * np.clip(1 - lower / np.maximum(amp * 0.6, 1e-9), 0, 1)
        independent *= np.clip(peak_ratio / 0.025, 0, 1)
        fundamental = np.zeros(shape)
        np.add.at(fundamental, (frames, pitch_class), independent * note_weight)
        # Drum resonances can look like individual pitch classes. Check that
        # midrange peaks cluster around semitones before pooling across beats.
        mid_weight = independent * np.clip((hz - 65) / 75, 0, 1)
        tuning = np.column_stack((
            np.bincount(frames, mid_weight * np.cos(2 * np.pi * midi), minlength=len(mag)),
            np.bincount(frames, mid_weight, minlength=len(mag)),
        ))
        chroma_blocks.append(chroma)
        bass_blocks.append(bass)
        fundamental_blocks.append(fundamental)
        tuning_blocks.append(tuning)
        balanced_blocks.append(balanced)
    return tuple(np.concatenate(blocks) for blocks in (
        chroma_blocks, bass_blocks, fundamental_blocks, tuning_blocks, balanced_blocks
    ))


def _subdivision_phase(events, low_flux, y):
    """Identify a fast grid whose alternating quiet ticks subdivide the pulse.

    A kick/snare color change by itself is insufficient: the weaker half must
    also have consistently much less acoustic energy than the stronger attacks.
    """
    if len(events) < 10 or np.median(np.diff(events)) >= 60 / 145:
        return None
    low, amplitude = [], []
    for t in events:
        start, end = max(0, t - 0.04), t + 0.075
        a, b = round(start * _SR / _HOP), round(end * _SR / _HOP) + 1
        low.append(float(low_flux[a:b].max(initial=0)))
        seg = y[round(start * _SR) : round(end * _SR)]
        amplitude.append(float(np.sqrt(np.mean(seg * seg))) if len(seg) else 0.0)
    low, amplitude = np.asarray(low), np.asarray(amplitude)
    phase = int(np.median(low[1::2]) > np.median(low[::2]))
    strong = amplitude[phase::2]
    weak = amplitude[1 - phase :: 2]
    if (
        np.median(low[phase::2]) > 2.6 * max(1e-7, np.median(low[1 - phase :: 2]))
        and np.median(strong) > 1.9 * max(1e-7, np.median(weak))
        and np.percentile(strong, 25) > 1.30 * np.percentile(weak, 75)
    ):
        return phase
    return None


def _continued_quarter_curve(tempo_curve, frames, peaks, onset, frame_s):
    """Recover a continuing quarter pulse when a dotted-quarter accent takes over."""
    curve = tempo_curve.copy()
    jumps = 1 + np.flatnonzero(abs(np.diff(np.log(curve))) > np.log(1.18))
    boundaries = np.r_[0, jumps, len(curve)]
    changed = False
    for previous, first, last in zip(boundaries, boundaries[1:], boundaries[2:]):
        old_bpm = float(np.median(curve[previous:first]))
        new_bpm = float(np.median(curve[first:last]))
        if not 1.43 <= old_bpm / new_bpm <= 1.57:
            continue
        # Fit the phase and the actual inter-beat interval on both sides of
        # the initial estimate's quantization error, using only earlier beats.
        prior = frames[(frames >= previous) & (frames < first)][-16:].astype(float)
        if len(prior) < 5:
            continue
        nominal = 60 / old_bpm / frame_s
        numbers = np.rint((prior - prior[-1]) / nominal)
        offsets = prior - numbers * nominal
        regular = abs(offsets - np.median(offsets)) < 0.10 * nominal
        if regular.sum() < 5:
            continue
        period, anchor = np.polyfit(numbers[regular], prior[regular], 1)
        if not 0.96 * nominal < period < 1.04 * nominal:
            continue

        # In a genuine 3:2 slowdown just one in three earlier quarters normally
        # coincides with the new pulse. Require consistent attacks in each
        # local window and stronger support on that phase than between beats.
        stop = min(len(onset), max(last, first + round(6 * period)))
        ticks = np.arange(np.ceil((first - anchor) / period), np.ceil((stop - anchor) / period))
        local = peaks[(peaks >= first - 2) & (peaks < stop + 2)]
        if len(ticks) < 4 or len(local) < 3:
            continue
        threshold = max(0.0005, float(np.percentile(onset[local], 75)) * 0.18)
        hits = local[onset[local] >= threshold]
        if not len(hits):
            continue
        grid = anchor + ticks[:, None] * period
        probes = grid + np.array([0.0, -0.25, 0.25]) * period
        indices = np.searchsorted(hits, probes)
        before = hits[np.maximum(0, indices - 1)]
        after = hits[np.minimum(len(hits) - 1, indices)]
        distance = np.minimum(abs(before - probes), abs(after - probes))
        matches = distance <= min(0.065 / frame_s, 0.10 * period)
        on_beat = matches[:, 0]
        windows = np.array_split(on_beat, max(1, len(on_beat) // 8))
        if (on_beat.mean() >= 0.64 and on_beat.mean() > matches[:, 1:].mean() + 0.12
                and all(window.mean() >= 0.60 for window in windows)):
            curve[first:last] = 60 / (period * frame_s)
            changed = True
    return curve if changed else None


def _beat_positions(onset, low_flux, y, start, duration, override):
    frame_s = _HOP / _SR
    active = onset[int(start / frame_s) :]
    maximum = float(active.max(initial=0))
    peaks, _ = signal.find_peaks(
        onset, distance=max(1, round(0.075 / frame_s)), prominence=max(maximum * 0.025, 0.0001)
    )
    evidence = len(peaks) >= 3 and maximum > 0.0005
    if override is not None:
        tempo = float(override)
        if not np.isfinite(tempo) or not 25 <= tempo <= 300:
            raise ValueError("Tempo 25 ile 300 BPM arasında olmalı.")
    else:
        tempo = 100.0
    events = np.array([], dtype=float)
    if evidence:
        # Track changes in local tempo on longer passages, instead of snapping
        # every bar to one global BPM. Median filtering prevents octave flips.
        if override is not None:
            bpm_for_tracking = tempo
        elif duration - start >= 10:
            # Overlapping blocks keep a long recording's tempogram out of RAM.
            curve = np.empty_like(onset)
            block, margin = round(75 / frame_s), round(6 / frame_s)
            for i in range(0, len(onset), block):
                begin, end = max(0, i - margin), min(len(onset), i + block)
                local = librosa.feature.tempo(
                    onset_envelope=onset[begin : end + margin],
                    sr=_SR,
                    hop_length=_HOP,
                    aggregate=None,
                    ac_size=6.0,
                )
                curve[i:end] = local[i - begin : end - begin]
            curve = ndimage.median_filter(curve, size=91, mode="nearest")
            # Eighth notes at a fill or at the padded end of the tempogram can
            # momentarily win at twice the underlying pulse. Resolve that
            # metrical ambiguity before dynamic programming lays out the beats.
            center = np.median(curve)
            curve = np.where(curve > center * 1.72, curve / 2, curve)
            curve = np.where(curve < center / 1.72, curve * 2, curve)
            bpm_for_tracking = curve
        else:
            bpm_for_tracking = None
        _, frames = librosa.beat.beat_track(
            onset_envelope=onset, sr=_SR, hop_length=_HOP, bpm=bpm_for_tracking, trim=False
        )
        if isinstance(bpm_for_tracking, np.ndarray):
            corrected = _continued_quarter_curve(bpm_for_tracking, frames, peaks, onset, frame_s)
            if corrected is not None:
                _, frames = librosa.beat.beat_track(
                    onset_envelope=onset, sr=_SR, hop_length=_HOP, bpm=corrected, trim=False
                )
        events = np.asarray(frames, dtype=float) * frame_s
        events = events[(events >= start - 0.08) & (events < duration)]
    if len(events) >= 3:
        period = 60 / tempo if override is not None else float(np.median(np.diff(events)))
        # Match consistent nearby transients. The centered spectra mark a sharp
        # onset about one hop early. Measured beat-to-beat times remain intact.
        candidates = peaks * frame_s + frame_s
        adjusted = events.copy()
        for i, t in enumerate(events):
            hits = np.flatnonzero(np.abs(candidates - t) <= min(0.08, period * 0.14))
            if len(hits):
                best = hits[np.argmax(onset[peaks[hits]])]
                adjusted[i] = candidates[best]
        events = adjusted
        if override is None:
            phase = _subdivision_phase(events, low_flux, y)
            if phase is not None:
                events = events[phase::2]
        period = 60 / tempo if override is not None else float(np.median(np.diff(events)))
        if override is not None:
            # Manual BPM is an exact quarter-note tempo; only its phase is inferred.
            residual = events - np.arange(len(events)) * period
            phase = float(np.median(residual[: min(12, len(residual))]))
            events = np.arange(phase, duration + period, period)
        while events[0] - period >= start - 0.085:
            events = np.r_[events[0] - period, events]
        events = events[events >= start - 0.085]
        if abs(events[0] - start) < min(0.10, 0.22 * period):
            events[0] = start
        if events[0] < start:
            events[0] = start
        if override is None:
            # A straight click should produce a straight MIDI tempo, unaffected
            # by the analysis hop. Keep real accelerations and tempo changes.
            slots = np.arange(len(events))
            fitted_period, intercept = np.polyfit(slots, events, 1)
            residual = np.abs(events - (intercept + slots * fitted_period))
            if np.percentile(residual, 90) <= min(0.035, period * 0.075):
                tempo = float(60 / fitted_period)
                rounded = round(tempo)
                if rounded and abs(60 / rounded - fitted_period) * len(events) < 0.028:
                    tempo = float(rounded)
                period = 60 / tempo
                if abs(intercept - start) < 0.025:
                    intercept = start
                end_aligned = duration - round((duration - intercept) / period) * period
                if abs(end_aligned - intercept) < 0.014 and end_aligned >= 0:
                    intercept = end_aligned
                events = np.maximum(0, intercept + slots * period)
            else:
                # Report the longest-supported local tempo rather than an unused
                # intermediate value between two equally sized tempo sections.
                intervals = ndimage.median_filter(np.diff(events), size=5, mode="nearest")
                ordered = np.sort(intervals)
                left = np.searchsorted(ordered, intervals * 0.972)
                right = np.searchsorted(ordered, intervals * 1.028)
                support = intervals * (right - left)
                best = int(np.argmax(support))
                tempo = float(60 / np.median(ordered[left[best] : right[best]]))
        peak_t = peaks * frame_s
        near = np.searchsorted(peak_t, events)
        left = peak_t[np.clip(near - 1, 0, len(peaks) - 1)]
        right = peak_t[np.clip(near, 0, len(peaks) - 1)]
        confidence = float(np.mean(np.minimum(abs(events - left), abs(events - right)) < 0.09))
        # Dense broadband noise has an apparent transient near every possible
        # grid. Also require a repeated pulse at a plausible lag.
        periodicity = []
        for window_start in range(0, len(active), 600):
            chunk = active[window_start : window_start + 600].astype(float)
            if len(chunk) < 100 or chunk.max() < maximum * 0.05:
                continue
            chunk -= chunk.mean()
            ac = signal.correlate(chunk, chunk, mode="full", method="fft")[len(chunk) - 1 :]
            lag = 60 / tempo / frame_s
            region = ac[max(1, int(lag * 0.80)) : min(len(ac), int(lag * 1.22) + 1)]
            if region.size and ac[0] > 1e-9:
                periodicity.append(float(region.max() / ac[0]))
        if periodicity:
            confidence *= float(np.clip(2.25 * np.median(periodicity), 0, 1))
        last_period = period if override is not None else float(np.median(np.diff(events)[-6:]))
    else:
        last_period = 60 / tempo
        events = np.array([start])
        confidence = 0.0
    if override is not None:
        anchor = events[0]
        end_aligned = duration - round((duration - anchor) / last_period) * last_period
        if abs(end_aligned - anchor) < 0.014 and end_aligned >= 0:
            anchor = end_aligned
        events = (
            anchor
            + np.arange(max(2, 1 + int(np.ceil((duration - anchor) / last_period)))) * last_period
        )
    near_end = np.flatnonzero(abs(events - duration) <= min(0.045, 0.10 * last_period))
    if len(near_end) and near_end[0] > 0:
        events = events[: near_end[0] + 1]
        events[-1] = duration
    elif events[-1] < duration:
        count = int(np.ceil((duration - events[-1]) / last_period))
        events = np.r_[events, events[-1] + last_period * np.arange(1, count + 1)]
        if len(events) > 2 and duration - events[-2] <= min(0.045, 0.10 * last_period):
            events = events[:-1]
            events[-1] = duration
    if events[-1] < duration:
        events[-1] = duration
    if len(events) < 2:
        events = np.array([start, max(duration, start + last_period)])
    return events, tempo, confidence


def _beat_vectors(chroma, bass, beats):
    frame_s = _CHROMA_HOP / _SR
    notes, lows = [], []
    for a, b in zip(beats[:-1], beats[1:]):
        lo = min(len(chroma) - 1, max(0, round((a + 0.10 * (b - a)) / frame_s)))
        hi = min(len(chroma), max(lo + 1, round((b - 0.08 * (b - a)) / frame_s)))
        notes.append(chroma[lo:hi].mean(axis=0))
        lows.append(bass[lo:hi].mean(axis=0))
    notes, lows = np.asarray(notes), np.asarray(lows)
    return notes, lows


def _unit(matrix):
    return matrix / np.maximum(np.linalg.norm(matrix, axis=-1, keepdims=True), 1e-9)


def _decode_chords(notes, lows):
    x = _unit(notes)
    bass = lows / np.maximum(lows.max(axis=1, keepdims=True), 1e-9)
    scores = x @ _TRIADS.T + 0.14 * np.tile(bass, (1, 2))
    # Repeated evidence across beats can establish an ambiguous chord.
    # A clear new root or quality is allowed to change inside a bar.
    trace = np.empty(scores.shape, dtype=int)
    value = scores[0].copy()
    for i in range(1, len(scores)):
        previous = int(np.argmax(value))
        stay = value >= value[previous] - 0.15
        trace[i] = np.where(stay, np.arange(24), previous)
        value = np.maximum(value, value[previous] - 0.15) + scores[i]
    sequence = np.empty(len(scores), dtype=int)
    sequence[-1] = int(value.argmax())
    for i in range(len(sequence) - 1, 0, -1):
        sequence[i - 1] = trace[i, sequence[i]]
    quality = []
    names = []
    for i, idx in enumerate(sequence):
        root = idx % 12
        third = (root + (3 if idx >= 12 else 4)) % 12
        fifth = (root + 7) % 12
        triad = x[i, [root, third, fifth]]
        quality.append(min(triad) / max(max(triad), 1e-8))
        names.append(_NAMES[root] + ("m" if idx >= 12 else ""))
    return names, np.asarray(quality), sequence


def _supported_chords(notes, lows, fundamentals, simultaneous, tuning, balanced):
    """Recognize local triads and open fifths while leaving weak beats blank."""
    names, quality, sequence = _decode_chords(notes, lows)
    strength = (_unit(notes) @ _TRIADS.T).max(axis=1)
    level = notes.sum(axis=1)
    active = level > level.max() * 0.04
    pitch = fundamentals / np.maximum(fundamentals.sum(axis=1, keepdims=True), 1e-9)
    kernel = np.array([1, 2, 3, 2, 1]) / 9
    local_pitch = ndimage.convolve1d(pitch, kernel, axis=0, mode="nearest")
    tuning_score = tuning[:, 0] / np.maximum(tuning[:, 1], 1e-9)
    tuned = ndimage.convolve1d(tuning_score, kernel, mode="nearest") > 0.11

    def tones(seq):
        return np.column_stack((seq % 12, (seq + np.where(seq >= 12, 3, 4)) % 12, (seq + 7) % 12))

    direct = (quality > 0.15) & (strength > 0.72)
    direct_tones = np.take_along_axis(pitch, tones(sequence), axis=1)
    direct &= (direct_tones[:, 1] > 0.045) & (np.sort(direct_tones, axis=1)[:, 1] > 0.08)
    # Preserve individual strong chord changes and short soft transitions in
    # tonal music, even when neighboring beats have a different chord.
    reliable = np.count_nonzero(direct & active & tuned) >= 0.32 * max(1, np.count_nonzero(active))
    if reliable:
        nearby = ndimage.uniform_filter1d(direct.astype(float), size=3, mode="nearest")
        direct |= (nearby >= 0.66) & (quality > 0.08) & (strength > 0.68)

    # Equally weight each beat so one loud pluck cannot determine the next
    # chord. Require supporting tones on this beat as well as in its neighbors.
    relative_notes = notes / np.maximum(level[:, None], 1e-9)
    upper_notes = balanced / np.maximum(balanced.sum(axis=1, keepdims=True), 1e-9)
    local_notes = ndimage.convolve1d((relative_notes + upper_notes) * 0.5, kernel, axis=0, mode="nearest")
    local_lows = ndimage.convolve1d(lows, kernel, axis=0, mode="nearest")
    local_names, local_quality, local_sequence = _decode_chords(local_notes, local_lows)
    local_tones = tones(local_sequence)
    local_strength = (_unit(local_notes) @ _TRIADS.T).max(axis=1)
    if not reliable:
        # A file with a long sparse verse can still have a clean, isolated
        # chord attack. Keep it when the nearby profile supports the same label.
        direct &= tuned & (sequence == local_sequence) & (local_quality > 0.15) & (local_strength > 0.70)
        direct &= np.take_along_axis(local_pitch, local_tones, axis=1)[:, 1] > 0.08
    local = (local_quality > 0.22) & (local_strength > 0.73)
    local &= np.take_along_axis(local_pitch, local_tones, axis=1).min(axis=1) > 0.07
    present = np.take_along_axis(pitch, local_tones, axis=1)

    def repeated(candidates, labels):
        neighbors = candidates[:-1] & candidates[1:] & (labels[:-1] == labels[1:])
        return np.r_[False, neighbors] | np.r_[neighbors, False]

    local = repeated(local & active & tuned, local_sequence)
    local &= (present.sum(axis=1) > 0.35) & (np.sort(present, axis=1)[:, 1] > 0.08)
    fifths = (np.arange(12) + 7) % 12
    fifth_pitch = local_pitch[:, fifths]
    pair = local_pitch + fifth_pitch
    weaker = np.minimum(local_pitch, fifth_pitch)
    balance = weaker / np.maximum(np.maximum(local_pitch, fifth_pitch), 1e-9)
    roots = np.argmax(pair * balance ** 0.24, axis=1)
    row = np.arange(len(pitch))
    third = np.maximum(local_pitch[row, (roots + 3) % 12], local_pitch[row, (roots + 4) % 12])
    dyad = (pair[row, roots] > 0.56) & (weaker[row, roots] > 0.12) & (third < 0.10)
    beat_pair = pitch[row, roots] + pitch[row, fifths[roots]]
    beat_weaker = np.minimum(pitch[row, roots], pitch[row, fifths[roots]])
    beat_third = np.maximum(pitch[row, (roots + 3) % 12], pitch[row, (roots + 4) % 12])
    attack = (beat_pair > 0.62) & (beat_weaker > 0.14) & (beat_third < 0.09)
    dyad = repeated((dyad | attack) & active & tuned, roots)
    dyad &= (beat_pair > 0.40) & (beat_weaker > 0.08)
    dyad &= simultaneous[row, roots] >= 0.30
    dyad &= repeated(dyad, roots) | ((simultaneous[row, roots] >= 0.65) & attack)
    chord_names = [
        names[i] if direct[i] else local_names[i] if local[i] else _NAMES[roots[i]] + "5" if dyad[i] else ""
        for i in row
    ]
    chord_names = [name if ok else "" for name, ok in zip(chord_names, active)]
    coverage = sum(bool(name) for name in chord_names) / max(1, np.count_nonzero(active))
    # An open fifth contains no third. A few local triads likewise cannot
    # establish the key of a whole recording with confidence.
    key = _key(notes[active], sequence[active]) if reliable else ""
    return chord_names, float(coverage), key


def _choose_meter(signature, beats, onset, low_flux, x):
    contrast = np.r_[0, np.maximum(0, 1 - np.sum(x[1:] * x[:-1], axis=1))]
    kinds = []
    if signature is None or str(signature).strip().lower() in {"auto", "otomatik", ""}:
        kinds = ["4/4", "3/4"]
    else:
        try:
            num, den = map(int, str(signature).split("/"))
            if not (1 <= num <= 32 and den in {1, 2, 4, 8, 16}):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("Ölçü 4/4 veya 7/8 gibi yazılmalı.") from None
        kinds = [f"{num}/{den}"]
    beat_indices = np.arange(len(x), dtype=float)
    attack = []
    energy = onset + low_flux
    for t in beats[:-1]:
        i = int(round(t * _SR / _HOP))
        a = max(0, min(i - 5, len(onset) - 1))
        b = min(len(onset), i + 6)
        attack.append(np.max(energy[a : max(a + 1, b)]))
    attack = np.array(attack)
    # Ignore the first arbitrary attack when estimating meter phase.
    if len(attack) > 1:
        attack[0] = np.median(attack[1:])
    scaled_attack = np.maximum(0, attack - np.percentile(attack, 40))
    variations = contrast > max(0.045, np.median(contrast) * 2)
    contrasts = np.where(variations, np.minimum(contrast, 0.20), 0)
    positions = []
    for kind in kinds:
        numerator, denominator = map(int, kind.split("/"))
        width = numerator * 4 / denominator
        phases = np.arange(0, width, min(1, 4 / denominator))
        cand = []
        for phase in phases:
            delta = abs((beat_indices - phase + width / 2) % width - width / 2)
            hit = np.maximum(0, 1 - 1.5 * delta)
            # Subtract chance agreement so shorter candidate bars have no advantage.
            chance = float(hit[1:].mean()) if len(hit) > 1 else 0
            harmonic = 0
            if contrasts.any() and chance > 0:
                share = float(np.sum(hit * contrasts) / contrasts.sum())
                harmonic = (share / chance - 1) / width
            accent = (
                float(np.sum(hit * scaled_attack) / max(1e-9, scaled_attack.sum()) - hit.mean())
                if scaled_attack.any()
                else 0
            )
            evidence = harmonic * min(1, contrasts.sum() / 0.45) + 0.42 * accent
            if phase == 0:
                evidence += 0.065  # prefer no pickup when phase hypotheses are tied
            cand.append((evidence, float(phase)))
        best = max(cand, key=lambda c: c[0])
        positions.append((best[0], kind, best[1]))
    if len(positions) == 1:
        score, kind, phase = positions[0]
        return kind, phase, float(np.clip(score, 0, 1))
    quad, triple = positions
    # A weak or very short 3/4 hypothesis does not override the common 4/4 prior.
    choose_triple = len(x) >= 8 and triple[0] > quad[0] + 0.14 and triple[0] > 0.19
    score, kind, phase = triple if choose_triple else quad
    confidence = float(np.clip(score, 0, 1))
    return kind, phase, confidence


def _key(notes, sequence):
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    hist = notes.sum(axis=0)
    hist = hist - hist.mean()
    scores = []
    for idx in range(24):
        template = major if idx < 12 else minor
        profile = np.roll(template - template.mean(), idx % 12)
        corr = np.dot(hist, profile) / max(np.linalg.norm(hist) * np.linalg.norm(profile), 1e-12)
        scores.append(corr + 0.05 * (idx == sequence[0]) + 0.05 * (idx == sequence[-1]))
    best = int(np.argmax(scores))
    return _NAMES[best % 12] + (" minor" if best >= 12 else " major")


def _section_energy(rms, block_s, beats, gate):
    """Estimate sustained changes in backing level from the existing RMS envelope."""
    edges = np.clip(np.rint(beats / block_s).astype(int), 0, len(rms))
    levels = np.array([
        np.percentile(rms[a:b], 65) if b > a else 0.0
        for a, b in zip(edges, edges[1:])
    ])
    if not np.any(levels > gate):
        return [0.5] * len(levels)
    db = 20 * np.log10(np.maximum(levels, 1e-8))
    smooth = ndimage.median_filter(db, size=3, mode="nearest")
    center = np.median(smooth[levels > gate])
    change = smooth - center
    # A small backbeat/attack fluctuation is neutral. A section-level change
    # of about 9 dB can span the full expressive range.
    excursion = np.sign(change) * np.maximum(0.0, abs(change) - 1.5)
    return np.clip(0.5 + excursion / 15.0, 0.0, 1.0).tolist()


def analyze_song_timeline(
    path: str | Path, time_signature: str = "auto", bpm: float | None = None,
    *, first_downbeat_s: float | None = None,
) -> SongTimeline:
    """Analyze a whole excerpt, including pickups and its final partial bar.

    A blank chord means insufficient harmonic evidence. In particular, do not
    use drum transients or a single bass pitch as evidence of a major/minor key.
    A signature override selects the grouping but still estimates its phase.
    """
    y, _ = librosa.load(str(path), sr=_SR, mono=True)
    if not len(y) or not np.isfinite(y).all():
        raise ValueError("Ses kaydı boş veya okunamıyor.")
    duration = len(y) / _SR
    if first_downbeat_s is not None and not 0 <= first_downbeat_s < duration:
        raise ValueError("İlk ölçü başı kaydın süresi içinde olmalı.")
    if duration < 0.18 or abs(y).max() < 1e-6:
        raise ValueError("Ses kaydı çok kısa veya sessiz.")
    block = 110
    padded = np.pad(y, (0, (-len(y)) % block))
    rms = np.sqrt(np.mean(padded.reshape(-1, block) ** 2, axis=1))
    gate = max(float(np.percentile(rms, 90)) * 0.023, float(rms.max()) * 0.0005, 1e-7)
    audible = np.flatnonzero(rms > gate)
    start = float(audible[0] * block / _SR)
    if duration - start < 0.15:
        raise ValueError("Kayıtta analiz edilebilecek uzunlukta ses bulunamadı.")
    onset, low_flux = _rhythm(y)
    beats, tempo, pulse_conf = _beat_positions(onset, low_flux, y, start, duration, bpm)
    if first_downbeat_s is not None and bpm is not None:
        period = 60 / tempo
        leading = max(0, int(np.floor((first_downbeat_s - start) / period)))
        first = first_downbeat_s - leading * period
        count = max(1, int(np.ceil((duration - first) / period - 1e-4)))
        beats = first + np.arange(count + 1) * period
        if duration - beats[-1] > .0001:
            beats = np.r_[beats, duration]
    elif first_downbeat_s is not None and first_downbeat_s < beats[0]:
        beats = np.r_[first_downbeat_s, beats]
    chroma, bass, fundamentals, frame_tuning, balanced = _harmony(y)
    notes, lows = _beat_vectors(chroma, bass, beats)
    # Count evidence throughout the beat. One loud attack just across a beat
    # boundary must not label an otherwise unpitched or silent interval.
    fundamentals /= np.maximum(fundamentals.sum(axis=1, keepdims=True), 1e-9)
    simultaneous = (fundamentals > 0.08) & (np.roll(fundamentals, -7, axis=1) > 0.08)
    evidence, tuning = _beat_vectors(np.column_stack((fundamentals, simultaneous, balanced)), frame_tuning, beats)
    beat_names, tonal_conf, key = _supported_chords(notes, lows, evidence[:, :12], evidence[:, 12:24], tuning, evidence[:, 24:])
    supplemented = fill_sparse_chords(
        path, beats, beat_names, fundamentals, frame_tuning, chroma.sum(axis=1), _CHROMA_HOP / _SR
    )
    chordino_used = supplemented != beat_names
    if chordino_used:
        beat_names = supplemented
        tonal_conf = sum(map(bool, beat_names)) / len(beat_names)
    x = _unit(notes)
    has_harmony = any(beat_names)
    sig, phase, meter_conf = _choose_meter(
        time_signature, beats, onset, low_flux, x if has_harmony else np.zeros_like(x)
    )
    if pulse_conf < 0.28:
        meter_conf = min(meter_conf, 0.12)
    num, den = map(int, sig.split("/"))
    width = num * 4 / den
    coordinates = np.arange(len(beats), dtype=float)
    if first_downbeat_s is not None:
        phase = float(np.interp(first_downbeat_s, beats, coordinates))
        meter_conf = 1.
    bar_coords = np.arange(phase, len(beats) - 1 + 1e-8, width)
    actual = [
        (p, float(np.interp(p, coordinates, beats)))
        for p in bar_coords
        if np.interp(p, coordinates, beats) < duration - 0.001
    ]
    downbeat = actual[0][1] if actual else float(beats[0])
    exact = [int(round(p)) for p, _ in actual if abs(p - round(p)) < 1e-7]
    starts = [t for _, t in actual]
    if not starts or starts[0] > beats[0] + 0.001:
        starts.insert(0, float(beats[0]))
    ends = starts[1:] + [duration]
    bars = []
    for a, b in zip(starts, ends):
        weights = np.maximum(0, np.minimum(b, beats[1:]) - np.maximum(a, beats[:-1]))
        votes = {}
        for name, w in zip(beat_names, weights):
            if name and w > 0:
                votes[name] = votes.get(name, 0.0) + w
        # Two equal half-bar chords share the duration. Summaries name the
        # first one; the complete change remains available in beat_chords.
        if votes:
            maximum = max(votes.values())
            bars.append(next(name for name, w in votes.items() if maximum - w < 0.025))
        else:
            bars.append("")
    warnings = []
    if chordino_used:
        warnings.append("Belirsiz bölümlerdeki akorlar Chordino ile tahmin edildi.")
    if pulse_conf < 0.4:
        warnings.append("Vuruş tahmini zayıf; tempo ve başlangıcı kulakla kontrol edin.")
    if meter_conf < 0.18:
        warnings.append("Ölçü başı belirsiz; ölçü ve vurguları kontrol edin.")
    if not has_harmony:
        warnings.append("Armonik içerik güvenilir değil; akorları elle girin.")
    elif tonal_conf < 0.7 or beat_names.count("") >= 2:
        warnings.append(
            "Bazı bölümlerde akor tahmini zayıf; boş vuruşlar ve akor geçişlerini kontrol edin."
        )
    kicks, snares = _drum_cues(y, onset)
    return SongTimeline(
        duration,
        float(tempo),
        sig,
        start,
        beats.tolist(),
        downbeat,
        exact,
        starts,
        ends,
        bars,
        beat_names,
        key,
        tonal_conf,
        pulse_conf,
        meter_conf,
        warnings,
        kicks,
        snares,
        _section_energy(rms, block / _SR, beats, gate),
    )
