"""Run with python -m unittest discover -s scripts -p test_song_accompaniment.py."""
import tempfile
import unittest
from pathlib import Path

import mido
import numpy as np
import pretty_midi
import soundfile as sf

from data_prep.song_timeline import analyze_song_timeline
from model_symbolic.bass_groove_model import generate_song_bass_line
from modo_mapper.articulation_engine import ArticulationEngine, BassMelodyNote


class SongAccompanimentTest(unittest.TestCase):
    def test_modo_slide_and_concert_targets(self):
        melody = [
            BassMelodyNote(0, 380, 28, 85),
            BassMelodyNote(450, 980, 40, 93),
            BassMelodyNote(1000, 1630, 45, 85, "slide_up"),
            BassMelodyNote(1640, 1960, 43, 83, "slide_down"),
        ]
        engine = ArticulationEngine()
        with tempfile.TemporaryDirectory() as folder:
            mid = Path(folder) / "slide.mid"
            for target in ("modo", "concert"):
                engine.write_midi(melody, mid, target=target)
                with self.subTest(target=target):
                    messages = [m for m in mido.MidiFile(mid) if not m.is_meta and m.type != "program_change"]
                    events = [(m.type, tuple(m.bytes()[1:])) for m in messages]
                    live = []
                    for _, batch in engine.iter_realtime_messages(melody, target=target):
                        for kind, data in batch:
                            if kind == "pitchwheel":
                                absolute = data[0] + 8192
                                data = (absolute & 127, absolute >> 7)
                            live.append((kind, tuple(data)))
                    self.assertEqual(events, live)
                    notes = [m.note for m in messages if m.type == "note_on"]
                    if target == "modo":
                        self.assertEqual([n for n in notes if n >= 40], [40, 52, 57, 55])
                        self.assertTrue(any(m.type == "control_change" and m.control == 64 and m.value == 127 for m in messages))
                    else:
                        self.assertEqual(notes, [28, 40, 45, 43])
                    bends = [m.pitch for m in messages if m.type == "pitchwheel"]
                    self.assertGreater(max(bends), 0)
                    self.assertEqual(bends[-1], 0)

    def test_section_energy_preserves_quiet_and_loud_passages(self):
        from data_prep.song_timeline import _section_energy

        grid = np.arange(9) * .5
        quiet = np.tile([.012, .008, .013, .009, .011], 40)
        loud = quiet * 5
        levels = _section_energy(np.r_[quiet, loud], .01, grid, 1e-6)
        self.assertTrue(all(value < .25 for value in levels[:4]))
        self.assertTrue(all(value > .75 for value in levels[4:]))
        self.assertTrue(np.allclose(_section_energy(np.r_[loud, loud], .01, grid, 1e-6), .5))

    def test_pickup_chord_changes_and_midi_clock(self):
        rate, tempo, pickup = 22050, 90, 0.75
        chart = [(48, 52, 55), (45, 48, 52), (41, 45, 48), (43, 47, 50)] * 2
        duration = pickup + len(chart) * 4 * 60 / tempo
        audio = np.zeros(round(rate * duration))
        for beat in range(len(chart) * 4):
            start = round(rate * (pickup + beat * 60 / tempo))
            t = np.arange(round(rate * 0.55)) / rate
            envelope = np.minimum(1.0, t / .006) * np.exp(-6 * t)
            for pitch in chart[beat // 4]:
                hz = 440 * 2 ** ((pitch - 69) / 12)
                audio[start:start + len(t)] += .14 * np.sin(2 * np.pi * hz * t) * envelope
            # An eighth-note transient can otherwise double the tempo near EOF.
            offbeat = start + round(rate * 30 / tempo)
            tick = np.arange(round(rate * .04)) / rate
            audio[offbeat:offbeat + len(tick)] += .07 * np.sin(2 * np.pi * 3200 * tick) * np.exp(-80 * tick)

        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder) / "backing.wav"
            midi = Path(folder) / "bass.mid"
            sf.write(wav, audio, rate)
            song = analyze_song_timeline(wav)
            self.assertEqual(song.time_signature, "4/4")
            self.assertEqual(song.chords, ["C", "Am", "F", "G"] * 2)
            self.assertAlmostEqual(song.bpm, tempo, delta=1)
            notes = generate_song_bass_line(
                beat_times_ms=np.array(song.beat_times_s) * 1000,
                beat_chords=song.beat_chords, downbeat_indices=song.downbeat_indices,
                downbeat_times_ms=np.array(song.bar_starts_s) * 1000,
                duration_ms=song.duration_s * 1000, bpm=song.bpm,
                time_signature=song.time_signature, force_rules=True, seed=5,
            )
            melody = [BassMelodyNote(n.start_ms, n.end_ms, n.pitch, n.velocity) for n in notes]
            ArticulationEngine().write_midi(
                melody, midi, bpm=song.bpm, time_signature=song.time_signature, target="concert",
                beat_times_s=song.beat_times_s, downbeat_s=song.downbeat_s, duration_s=song.duration_s,
            )
            imported = pretty_midi.PrettyMIDI(str(midi))
            pitches = [n for n in imported.instruments[0].notes if n.pitch >= 28]
            self.assertAlmostEqual(min(n.start for n in pitches), pickup, delta=.04)
            for index, chord in enumerate(chart):
                bar = pickup + index * 4 * 60 / tempo
                hit = min(pitches, key=lambda n: abs(n.start - bar))
                self.assertAlmostEqual(hit.start, bar, delta=.06)
                self.assertEqual(hit.pitch % 12, chord[0] % 12)
            self.assertLess(max(abs(imported.get_tempo_changes()[1] - tempo)), 1.5)
            self.assertAlmostEqual(mido.MidiFile(midi).length, duration, delta=.005)


if __name__ == "__main__":
    unittest.main()
