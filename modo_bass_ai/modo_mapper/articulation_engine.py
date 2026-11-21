"""Convert raw bass melody events into MODO BASS 2 MIDI with keyswitches + CC."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import mido
import numpy as np
import pretty_midi

logger = logging.getLogger(__name__)

# Default relative to package root
_DEFAULT_MAP = Path(__file__).resolve().parent.parent / "config" / "modo_bass_map.json"
_PPQ = 960


def _performance_clock(
    bpm: float,
    time_signature: str,
    beat_times_s: Sequence[float] | None,
    duration_s: float | None = None,
) -> tuple[pretty_midi.PrettyMIDI, mido.MidiTrack]:
    """Build the source clock. Beat anchors mark quarter notes even in compound meters."""
    if not np.isfinite(bpm) or bpm <= 0:
        raise ValueError("bpm must be positive and finite")
    numerator, denominator = map(int, time_signature.split("/"))
    if numerator < 1 or denominator < 1 or denominator & (denominator - 1):
        raise ValueError("Expected a positive MIDI time signature, e.g. 6/8")
    initial = mido.bpm2tempo(bpm)
    tempos = {0: initial}
    if beat_times_s is not None:
        beats = np.asarray(beat_times_s, dtype=float)
        if beats.ndim != 1 or not np.all(np.isfinite(beats)) or np.any(beats < 0):
            raise ValueError("beat_times_s must contain nonnegative, finite seconds")
        intervals = np.diff(beats)
        if np.any(intervals <= 0):
            raise ValueError("beat_times_s must be strictly increasing")
        if len(intervals):
            # Keep the pickup at its source time. Each later anchor is exactly
            # one quarter note (PPQ ticks) after the previous anchor.
            first_tick = mido.second2tick(beats[0], _PPQ, initial)
            for i, interval in enumerate(intervals):
                if duration_s is not None and beats[i] >= duration_s:
                    break
                tempos[first_tick + i * _PPQ] = round(interval * 1_000_000)
    midi = mido.MidiFile(ticks_per_beat=_PPQ)
    track = midi.add_track()
    track.append(
        mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator)
    )
    last_tick, last_tempo = 0, None
    for tick, tempo in tempos.items():
        if tempo != last_tempo:
            if not 0 < tempo <= 0xFFFFFF:
                raise ValueError(
                    "Quarter-note duration is outside the MIDI tempo range"
                )
            track.append(
                mido.MetaMessage("set_tempo", time=tick - last_tick, tempo=tempo)
            )
            last_tick, last_tempo = tick, tempo
    clock = BytesIO()
    midi.save(file=clock)
    clock.seek(0)
    return pretty_midi.PrettyMIDI(clock), track


@dataclass
class BassMelodyNote:
    """Raw melody note before MODO articulation enrichment."""

    start_ms: float
    end_ms: float
    pitch: int
    velocity: int
    articulation: str | None = None  # legato | slide | ghost | harmonic | None
    string_hint: str | None = None  # E|A|D|G
    is_passing: bool = False


@dataclass
class FretboardState:
    """Track last string / fret to avoid needless string jumps."""

    string_name: str = "A"
    fret: int = 0
    history: list[tuple[str, int]] = field(default_factory=list)


class ArticulationEngine:
    """Load MODO map JSON and emit a PrettyMIDI performance."""

    STRING_ORDER = ("E", "A", "D", "G")

    def __init__(self, map_path: str | Path | None = None) -> None:
        self.map_path = Path(map_path) if map_path else _DEFAULT_MAP
        self.cfg = self._load(self.map_path)
        self.ks = self.cfg["keyswitches"]
        self.strings = self.cfg["string_selection"]
        self.open_midi = {k: int(v) for k, v in self.cfg["open_string_midi"].items()}
        self.cc = self.cfg["cc"]
        self.timing = self.cfg["timing"]
        self.ghost_vel_max = int(self.timing.get("ghost_velocity_max", 40))
        self.state = FretboardState()
        policy = self.cfg.get("assumptions", {})
        self.channel = int(policy.get("channel", 1)) - 1
        if not 0 <= self.channel <= 15:
            raise ValueError("Configured MIDI channel must be 1 through 16")
        self.note_offset = int(policy.get("modo_note_offset", 12))
        self.wheel_range = float(policy.get("slide_range_semitones", 2))
        if not 0 < self.wheel_range <= 24:
            raise ValueError("MODO slide range must be in (0,24] semitones")

    @staticmethod
    def _load(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def choose_string(self, pitch: int, hint: str | None = None) -> tuple[str, int]:
        """Pick string + fret minimizing jump from last position."""
        if hint and hint in self.open_midi:
            open_p = self.open_midi[hint]
            fret = pitch - open_p
            if 0 <= fret <= 20:
                return hint, fret

        candidates: list[tuple[float, str, int]] = []
        for name in self.STRING_ORDER:
            open_p = self.open_midi[name]
            fret = pitch - open_p
            if fret < 0 or fret > 20:
                continue
            # Prefer staying near previous fret / adjacent string
            string_dist = abs(
                self.STRING_ORDER.index(name)
                - self.STRING_ORDER.index(self.state.string_name)
            )
            fret_dist = abs(fret - self.state.fret)
            cost = string_dist * 2.5 + fret_dist * 1.0
            # Prefer mid-neck for tone consistency
            cost += abs(fret - 5) * 0.15
            candidates.append((cost, name, fret))
        if not candidates:
            # Clamp into E-string range
            fret = max(0, min(20, pitch - self.open_midi["E"]))
            return "E", fret
        candidates.sort(key=lambda x: x[0])
        _, name, fret = candidates[0]
        return name, fret

    def _switch(self, inst, number, start, end):
        start = max(0.0, start)
        if end > start:
            inst.notes.append(
                pretty_midi.Note(self.timing["keyswitch_velocity"], number, start, end)
            )

    def _connection_strings(self, notes):
        """Force both ends of a connected gesture onto an available fretted string."""
        forced = [None] * len(notes)
        for i in range(1, len(notes)):
            before, now = notes[i - 1], notes[i]
            art = now.articulation
            interval = now.pitch - before.pitch
            if art not in {
                "slide",
                "slide_up",
                "slide_down",
                "legato",
                "hammer_on",
                "pull_off",
            }:
                continue
            if (
                not interval
                or now.start_ms - before.end_ms > 125
                or now.start_ms <= before.start_ms
            ):
                continue
            if art in {"slide_up", "hammer_on"} and interval < 0:
                continue
            if art in {"slide_down", "pull_off"} and interval > 0:
                continue
            candidates = [
                s
                for s, base in self.open_midi.items()
                if 1 <= min(before.pitch, now.pitch) - base
                and max(before.pitch, now.pitch) - base <= 20
            ]
            if forced[i - 1] in candidates:
                selected = forced[i - 1]
            elif candidates and not forced[i - 1]:
                selected = next(
                    (
                        s
                        for s in (now.string_hint, before.string_hint)
                        if s in candidates
                    ),
                    min(
                        candidates,
                        key=lambda s: abs(
                            min(now.pitch, before.pitch) - self.open_midi[s] - 5
                        ),
                    ),
                )
            else:
                continue
            forced[i - 1] = forced[i] = selected
        return forced

    @staticmethod
    def _scoop(inst, start, end, offset, span):
        """Approach the receiving pitch during a short part of its attack."""
        start_value = int(np.clip(round(offset / span * 8192), -8192, 8191))
        for i in range(11):
            u = i / 10
            # Smoothstep reaches the target with zero slope.
            value = round(start_value * (1 - u * u * (3 - 2 * u)))
            inst.pitch_bends.append(
                pretty_midi.PitchBend(value, start + u * (end - start))
            )

    @staticmethod
    def _vibrato(inst, number, start, end):
        length = end - start
        if length < 0.18:
            return
        for fraction, value in (
            (0, 0),
            (0.23, 0),
            (0.39, 28),
            (0.60, 54),
            (0.84, 54),
            (0.94, 26),
            (1, 0),
        ):
            inst.control_changes.append(
                pretty_midi.ControlChange(number, value, start + length * fraction)
            )

    def melody_to_midi(
        self,
        notes: Sequence[BassMelodyNote],
        play_style: str = "Fingerstyle",
        program: int = 33,
        *,
        bpm: float = 120.0,
        time_signature: str = "4/4",
        beat_times_s: Sequence[float] | None = None,
        target: str = "modo",
    ) -> pretty_midi.PrettyMIDI:
        """Return a seconds-based performance. write_midi also emits the configured channel."""
        pm, _ = _performance_clock(bpm, time_signature, beat_times_s)
        pm.instruments.append(
            self._performance_instrument(notes, play_style, program, target)
        )
        return pm

    def _performance_instrument(self, notes, play_style, program, target):
        if target not in {"modo", "concert"}:
            raise ValueError("target must be modo or concert")
        modo = target == "modo"
        inst = pretty_midi.Instrument(
            program, name="MODO Bass AI" if modo else "Concert Bass"
        )
        notes = sorted(notes, key=lambda n: n.start_ms)
        if not notes:
            return inst

        def control(number, value, at):
            inst.control_changes.append(
                pretty_midi.ControlChange(number, value, max(0.0, at))
            )

        inst.pitch_bends.append(pretty_midi.PitchBend(0, 0.0))
        control(self.cc["vibrato"] if modo else 1, 0, 0.0)
        if modo:
            control(self.cc["legato_slide"], 0, 0.0)
        else:
            # An ordinary GM receiver interprets this standard RPN as ±12 semitones.
            for number, value in (
                (101, 0),
                (100, 0),
                (6, 12),
                (38, 0),
                (101, 127),
                (100, 127),
            ):
                control(number, value, 0.0)
        base_style = self.cfg["play_styles"].get(play_style, "fingerstyle")
        last_style, mute_level = None, None
        forced = self._connection_strings(notes)
        legato_holds = []
        pre = self.timing.get("keyswitch_pre_roll_ms", 12) / 1000
        playable = []
        for i, n in enumerate(notes):
            start = max(0.0, n.start_ms / 1000)
            end = max(start + 0.003, n.end_ms / 1000)
            if i + 1 < len(notes):
                end = min(end, notes[i + 1].start_ms / 1000)
            if end <= start:
                continue
            at = max(0.0, start - min(pre, 0.24 * (end - start)))
            pitch = int(np.clip(n.pitch, 28, 67))
            velocity = int(np.clip(n.velocity, 1, 127))
            art = n.articulation
            ghost = art in {"ghost", "dead_note"} or (
                art is None and velocity <= self.ghost_vel_max
            )
            if ghost:
                velocity = min(velocity, self.ghost_vel_max)
            if modo:
                style = "slap" if art in {"slap", "pop", "thumb"} else base_style
                if style != last_style:
                    self._switch(inst, self.ks[style], at, min(end, start + 0.023))
                    last_style = style
                mute = (
                    95
                    if art in {"palm_mute", "mute"}
                    else 72
                    if play_style == "Mute"
                    else 0
                )
                if mute != mute_level:
                    control(self.cc["palm_mute"], mute, at)
                    mute_level = mute
                # Ghost, harmonics and directed gestures are momentary controls.
                if ghost:
                    self._switch(inst, self.ks["ghost_note"], at, end)
                elif art in {"harmonic", "harmonics"} and pitch >= 40:
                    self._switch(inst, self.ks["harmonics"], at, end)
                    pitch -= 12  # MODO generates a harmonic one octave above its input.
                elif art in {"slap", "pop", "thumb"}:
                    self._switch(
                        inst, self.ks["pop" if art == "pop" else "thumb"], at, end
                    )
                string = forced[i] or n.string_hint
                if string in self.strings and 0 <= pitch - self.open_midi[string] <= 20:
                    self._switch(inst, self.strings[string], at, end)
            elif art in {"palm_mute", "mute"} or ghost or play_style == "Mute":
                end = min(end, start + (0.068 if ghost else 0.16))

            before = notes[i - 1] if i else None
            previous_out = playable[-1] if playable else None
            connected = bool(
                i
                and forced[i]
                and forced[i - 1] == forced[i]
                and previous_out
                and start - previous_out.end <= 0.13
            )
            interval = n.pitch - before.pitch if before else 0
            slide = art in {
                "slide",
                "slide_up",
                "slide_down",
                "slide_in_up",
                "slide_in_down",
            }
            if slide and not ghost:
                up = art.endswith("_up") or (art == "slide" and interval >= 0)
                delta = (
                    interval
                    if connected and (interval > 0) == up
                    else (2 if up else -2)
                )
                if (
                    modo
                    and connected
                    and abs(delta) > self.wheel_range
                    and (end - start) >= 0.15 + 0.05 * abs(delta)
                    and art not in {"slide_in_up", "slide_in_down"}
                ):
                    if legato_holds and at <= legato_holds[-1][1]:
                        legato_holds[-1] = (legato_holds[-1][0], end)
                    else:
                        legato_holds.append((at, end))
                    previous_out.end = start + min(0.022, (end - start) * 0.22)
                else:
                    span = self.wheel_range if modo else 12.0
                    length = min(end - start, 0.052 + 0.013 * min(abs(delta), 9))
                    self._scoop(
                        inst,
                        start,
                        start + length,
                        -np.sign(delta) * min(abs(delta), span),
                        span,
                    )
            elif art in {"legato", "hammer_on", "pull_off"} and connected:
                if modo:
                    self._switch(inst, self.ks["legato"], at, end)
                    previous_out.end = start + min(0.015, (end - start) * 0.2)
                else:
                    velocity = max(1, round(velocity * 0.91))
            if art == "vibrato":
                self._vibrato(inst, self.cc["vibrato"] if modo else 1, start, end)
            sounding = pretty_midi.Note(
                velocity, pitch + (self.note_offset if modo else 0), start, end
            )
            inst.notes.append(sounding)
            playable.append(sounding)
        if modo and mute_level:
            control(self.cc["palm_mute"], 0, playable[-1].end)
        if modo:
            for start, end in legato_holds:
                control(self.cc["legato_slide"], 127, start)
                control(self.cc["legato_slide"], 0, end)
            # Consecutive connected notes may request the same force-string key.
            # Coalesce held control notes to avoid a stray release during the pair.
            switches = set(self.ks.values()) | set(self.strings.values())
            merged, holds = [], {}
            for n in sorted(inst.notes, key=lambda item: item.start):
                previous = holds.get(n.pitch)
                if n.pitch in switches and previous and n.start < previous.end:
                    previous.end = max(previous.end, n.end)
                else:
                    merged.append(n)
                    if n.pitch in switches:
                        holds[n.pitch] = n
            inst.notes = merged
        return inst

    def _events(self, inst):
        """Single MIDI message ordering for realtime and Standard MIDI Files."""
        events = []
        for c in inst.control_changes:
            events.append((c.time, 1, "control_change", (c.number, c.value)))
        for b in inst.pitch_bends:
            events.append((b.time, 2, "pitchwheel", (b.pitch,)))
        for n in inst.notes:
            events.append((n.start, 3, "note_on", (n.pitch, n.velocity)))
            events.append((n.end, 0, "note_off", (n.pitch, 0)))
        return sorted(events, key=lambda e: (e[0], e[1]))

    def write_midi(
        self,
        notes: Sequence[BassMelodyNote],
        out_path: str | Path,
        play_style: str = "Fingerstyle",
        *,
        bpm: float = 120.0,
        time_signature: str = "4/4",
        beat_times_s: Sequence[float] | None = None,
        downbeat_s: float | None = None,
        duration_s: float | None = None,
        target: str = "modo",
    ) -> Path:
        """Export against the source clock, in MODO input or concert pitch."""
        for key, value in (("downbeat_s", downbeat_s), ("duration_s", duration_s)):
            if value is not None and (not np.isfinite(value) or value < 0):
                raise ValueError(f"{key} must be nonnegative and finite")
        if (
            duration_s is not None
            and downbeat_s is not None
            and downbeat_s > duration_s
        ):
            raise ValueError("downbeat_s cannot be later than duration_s")
        pm, conductor = _performance_clock(
            bpm, time_signature, beat_times_s, duration_s
        )
        if duration_s is not None:
            from dataclasses import replace

            notes = [
                replace(n, end_ms=min(n.end_ms, duration_s * 1000))
                for n in notes
                if n.start_ms < duration_s * 1000
            ]
        inst = self._performance_instrument(notes, play_style, 33, target)
        markers = mido.MidiTrack()
        if downbeat_s is not None:
            tick = pm.time_to_tick(downbeat_s)
            markers.append(mido.MetaMessage("marker", text="Downbeat", time=tick))
            if tick > 0:
                markers.append(conductor[0].copy(time=0))
        midi = mido.MidiFile(ticks_per_beat=_PPQ)
        midi.tracks.append(mido.merge_tracks([conductor, markers]))
        track = midi.add_track(inst.name)
        track.append(mido.Message("program_change", program=33, channel=self.channel))
        last_tick = 0
        for at, _, kind, data in self._events(inst):
            if duration_s is not None:
                at = min(at, duration_s)
            tick = pm.time_to_tick(at)
            fields = (
                {"note": data[0], "velocity": data[1]}
                if kind in {"note_on", "note_off"}
                else {"control": data[0], "value": data[1]}
                if kind == "control_change"
                else {"pitch": data[0]}
            )
            track.append(
                mido.Message(
                    kind, time=tick - last_tick, channel=self.channel, **fields
                )
            )
            last_tick = tick
        end_tick = pm.time_to_tick(duration_s) if duration_s is not None else last_tick
        track.append(
            mido.MetaMessage("end_of_track", time=max(0, end_tick - last_tick))
        )
        conductor = midi.tracks[0]
        conductor[-1].time = max(0, end_tick - sum(msg.time for msg in conductor[:-1]))
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        midi.save(str(out_path))
        return out_path

    def iter_realtime_messages(
        self,
        notes: Sequence[BassMelodyNote],
        play_style: str = "Fingerstyle",
        *,
        target: str = "modo",
    ) -> Iterable[tuple[float, list[tuple[str, tuple[int, ...]]]]]:
        """Yield timestamped note_on/off, control_change and signed pitchwheel messages."""
        from itertools import groupby

        inst = self._performance_instrument(notes, play_style, 33, target)
        for at, group in groupby(self._events(inst), key=lambda e: e[0]):
            yield float(at), [(kind, data) for _, _, kind, data in group]
