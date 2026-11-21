"""Convert raw bass melody events into MODO BASS 2 MIDI with keyswitches + CC."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pretty_midi

logger = logging.getLogger(__name__)

# Default relative to package root
_DEFAULT_MAP = Path(__file__).resolve().parent.parent / "config" / "modo_bass_map.json"


@dataclass
class BassMelodyNote:
    """Raw melody note before MODO articulation enrichment."""

    start_ms: float
    end_ms: float
    pitch: int
    velocity: int
    articulation: Optional[str] = None  # legato | slide | ghost | harmonic | None
    string_hint: Optional[str] = None  # E|A|D|G
    is_passing: bool = False


@dataclass
class FretboardState:
    """Track last string / fret to avoid needless string jumps."""

    string_name: str = "A"
    fret: int = 0
    history: List[Tuple[str, int]] = field(default_factory=list)


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
        self.cc_curves = self.cfg["cc_curves"]
        self.timing = self.cfg["timing"]
        self.ghost_vel_max = int(self.timing.get("ghost_velocity_max", 40))
        self.state = FretboardState()

    @staticmethod
    def _load(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    # ---------------------------------------------------------------- helpers
    def _pre_roll_ms(self) -> float:
        lo = float(self.timing["keyswitch_pre_roll_ms_min"])
        hi = float(self.timing["keyswitch_pre_roll_ms_max"])
        return float(np.random.uniform(lo, hi))

    def choose_string(self, pitch: int, hint: Optional[str] = None) -> Tuple[str, int]:
        """Pick string + fret minimizing jump from last position."""
        if hint and hint in self.open_midi:
            open_p = self.open_midi[hint]
            fret = pitch - open_p
            if 0 <= fret <= 20:
                return hint, fret

        candidates: List[Tuple[float, str, int]] = []
        for name in self.STRING_ORDER:
            open_p = self.open_midi[name]
            fret = pitch - open_p
            if fret < 0 or fret > 20:
                continue
            # Prefer staying near previous fret / adjacent string
            string_dist = abs(self.STRING_ORDER.index(name) - self.STRING_ORDER.index(self.state.string_name))
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

    def _ks_note(
        self,
        pitch: int,
        time_s: float,
        velocity: Optional[int] = None,
    ) -> pretty_midi.Note:
        vel = int(velocity if velocity is not None else self.timing["keyswitch_velocity"])
        return pretty_midi.Note(
            velocity=vel,
            pitch=int(pitch),
            start=max(0.0, time_s),
            end=max(0.0, time_s) + 0.03,
        )

    def _articulation_for(self, note: BassMelodyNote, prev: Optional[BassMelodyNote]) -> List[str]:
        arts: List[str] = []
        if note.velocity <= self.ghost_vel_max or note.articulation == "ghost":
            arts.extend(["ghost_note", "palm_mute"])
            return arts
        if note.articulation == "harmonic":
            arts.append("harmonics")
            return arts
        if note.articulation == "slide" and prev is not None:
            arts.append("slide")
            return arts
        if note.articulation in ("legato", "hammer_on", "pull_off") and prev is not None:
            interval = abs(note.pitch - prev.pitch)
            if interval <= 2:
                arts.append("legato")
            else:
                arts.append("slide")
            return arts
        # Auto: small interval + overlapping-ish timing → legato
        if prev is not None:
            gap_ms = note.start_ms - prev.end_ms
            interval = abs(note.pitch - prev.pitch)
            if gap_ms < 40 and 0 < interval <= 2:
                arts.append("legato")
            elif gap_ms < 60 and interval >= 3 and interval <= 7:
                arts.append("slide")
        return arts

    def _add_cc_curves(
        self,
        instrument: pretty_midi.Instrument,
        note: BassMelodyNote,
    ) -> None:
        dur = note.end_ms - note.start_ms
        if dur < float(self.cc_curves.get("long_note_ms_threshold", 480)):
            # Short notes: light expression plateau
            t0 = note.start_ms / 1000.0
            instrument.control_changes.append(
                pretty_midi.ControlChange(self.cc["expression"], 100, t0)
            )
            return

        vib = self.cc_curves["vibrato"]
        expr = self.cc_curves["expression"]
        start_s = note.start_ms / 1000.0
        end_s = note.end_ms / 1000.0
        n_steps = max(4, int(dur / 40.0))
        times = np.linspace(start_s, end_s, n_steps)

        vib_rise_at = start_s + (end_s - start_s) * float(vib["rise_fraction_of_duration"])
        expr_rise_at = start_s + (end_s - start_s) * float(expr["rise_fraction_of_duration"])

        for t in times:
            # Vibrato ramps after rise point
            if t < vib_rise_at:
                v_val = int(vib["start"])
            else:
                frac = (t - vib_rise_at) / max(1e-6, end_s - vib_rise_at)
                v_val = int(vib["start"] + frac * (vib["peak"] - vib["start"]))
            instrument.control_changes.append(
                pretty_midi.ControlChange(self.cc["vibrato"], int(np.clip(v_val, 0, 127)), float(t))
            )
            if t < expr_rise_at:
                e_val = int(expr["start"])
            else:
                frac = (t - expr_rise_at) / max(1e-6, end_s - expr_rise_at)
                e_val = int(expr["start"] + frac * (expr["peak"] - expr["start"]))
            instrument.control_changes.append(
                pretty_midi.ControlChange(self.cc["expression"], int(np.clip(e_val, 0, 127)), float(t))
            )

    # ----------------------------------------------------------------- main
    def melody_to_midi(
        self,
        notes: Sequence[BassMelodyNote],
        play_style: str = "Fingerstyle",
        program: int = 33,
    ) -> pretty_midi.PrettyMIDI:
        """Build a PrettyMIDI object with keyswitches + CC for MODO BASS 2."""
        pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        inst = pretty_midi.Instrument(program=program, name="MODO Bass AI")

        style_key = self.cfg.get("play_styles", {}).get(play_style, "fingerstyle")
        style_ks = int(self.ks.get(style_key, self.ks["fingerstyle"]))

        # Style keyswitch at t≈0
        inst.notes.append(self._ks_note(style_ks, 0.0))

        self.state = FretboardState()
        prev: Optional[BassMelodyNote] = None
        last_string_ks: Optional[str] = None

        for note in sorted(notes, key=lambda n: n.start_ms):
            pitch = int(np.clip(note.pitch, 28, 67))
            note = BassMelodyNote(
                start_ms=note.start_ms,
                end_ms=max(note.end_ms, note.start_ms + 30.0),
                pitch=pitch,
                velocity=int(np.clip(note.velocity, 1, 127)),
                articulation=note.articulation,
                string_hint=note.string_hint,
                is_passing=note.is_passing,
            )

            string_name, fret = self.choose_string(pitch, note.string_hint)
            self.state.string_name = string_name
            self.state.fret = fret
            self.state.history.append((string_name, fret))

            start_s = note.start_ms / 1000.0
            pre = self._pre_roll_ms() / 1000.0
            ks_t = max(0.0, start_s - pre)

            # String selection keyswitch only when string changes
            if string_name != last_string_ks:
                inst.notes.append(self._ks_note(int(self.strings[string_name]), ks_t - 0.005))
                last_string_ks = string_name

            arts = self._articulation_for(note, prev)
            # Stagger keyswitches slightly if multiple
            for i, art in enumerate(arts):
                ks_pitch = self.ks.get(art)
                if ks_pitch is None:
                    continue
                inst.notes.append(self._ks_note(int(ks_pitch), max(0.0, ks_t - i * 0.003)))

            # Sounding note
            vel = note.velocity
            if "ghost_note" in arts:
                vel = min(vel, self.ghost_vel_max)
            inst.notes.append(
                pretty_midi.Note(
                    velocity=vel,
                    pitch=pitch,
                    start=start_s,
                    end=note.end_ms / 1000.0,
                )
            )
            self._add_cc_curves(inst, note)
            prev = note

        pm.instruments.append(inst)
        return pm

    def write_midi(
        self,
        notes: Sequence[BassMelodyNote],
        out_path: str | Path,
        play_style: str = "Fingerstyle",
    ) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pm = self.melody_to_midi(notes, play_style=play_style)
        pm.write(str(out_path))
        return out_path

    def iter_realtime_messages(
        self,
        notes: Sequence[BassMelodyNote],
        play_style: str = "Fingerstyle",
    ) -> Iterable[Tuple[float, List[Tuple[str, Tuple[int, ...]]]]]:
        """Yield (absolute_time_seconds, [(msg_type, bytes_tuple), …]) for rtmidi streaming.

        msg_type in {'note_on','note_off','control_change'}.
        """
        pm = self.melody_to_midi(notes, play_style=play_style)
        events: List[Tuple[float, str, Tuple[int, ...]]] = []
        inst = pm.instruments[0]
        for n in inst.notes:
            events.append((n.start, "note_on", (n.pitch, n.velocity)))
            events.append((n.end, "note_off", (n.pitch, 0)))
        for cc in inst.control_changes:
            events.append((cc.time, "control_change", (cc.number, cc.value)))
        events.sort(key=lambda e: (e[0], 0 if e[1] == "control_change" else 1))

        # Group by time
        from itertools import groupby

        for t, group in groupby(events, key=lambda e: e[0]):
            msgs = [(g[1], g[2]) for g in group]
            yield float(t), msgs
