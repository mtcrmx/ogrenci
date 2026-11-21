"""Project-local Chordino fallback for tonal, polyphonic backing recordings."""

import csv
import io
import logging
import os
import re
import subprocess
from itertools import groupby
from pathlib import Path

import numpy as np

RUNTIME = Path(__file__).resolve().parents[1] / ".tools" / "chordino"
_CHORD = re.compile(
    r"[A-G][#b]?(?:maj7|m7b5|m7|m6|m|dim|aug|sus[24]|6|7|9)?(?:/[A-G][#b]?)?"
)
_LOG = logging.getLogger(__name__)


def _segment_labels(path, beats):
    host = RUNTIME / "sonic-annotator-win64" / "sonic-annotator.exe"
    plugins = RUNTIME / "plugins"
    if not host.is_file() or not (plugins / "nnls-chroma.dll").is_file():
        return None
    env = dict(os.environ, VAMP_PATH=str(plugins), VAMP_PATH_64=str(plugins))
    try:
        result = subprocess.run(
            [
                str(host),
                "-q",
                "-d",
                "vamp:nnls-chroma:chordino:simplechord",
                "-w",
                "csv",
                "--csv-stdout",
                str(Path(path).resolve(strict=True)),
            ],
            cwd=str(plugins),
            env=env,
            capture_output=True,
            check=True,
            timeout=min(180, max(12, beats[-1] * 0.40)),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        rows = list(
            csv.reader(io.StringIO(result.stdout.decode("utf-8-sig", errors="replace")))
        )
        starts = np.asarray([float(row[-2]) for row in rows if len(row) >= 3])
        names = [
            row[-1] if _CHORD.fullmatch(row[-1]) else ""
            for row in rows
            if len(row) >= 3
        ]
        if (
            not len(starts)
            or not np.isfinite(starts).all()
            or np.any(np.diff(starts) < 0)
        ):
            return None
    except (OSError, ValueError, csv.Error, subprocess.SubprocessError) as err:
        _LOG.warning("Local Chordino analysis unavailable: %s", err)
        return None
    # Require agreement at two positions within the beat, avoiding short
    # transition labels and allowing Chordino's no-chord intervals to stand.
    left = beats[:-1] + 0.25 * np.diff(beats)
    right = beats[:-1] + 0.70 * np.diff(beats)
    a = np.searchsorted(starts, left, side="right") - 1
    b = np.searchsorted(starts, right, side="right") - 1
    return [names[i] if i >= 0 and names[i] == names[j] else "" for i, j in zip(a, b)]


def fill_sparse_chords(path, beats, existing, pitch, tuning, level, frame_period):
    """Fill only locally supported beats of a polyphonic, sparsely labeled file.

    pitch contains normalized independent fundamental pitch classes for each
    spectral frame. A tuned second voice must occur simultaneously, so a
    monophonic melody that runs up a scale cannot imply a chord progression.
    """
    beats = np.asarray(beats)
    if len(existing) < 4 or sum(map(bool, existing)) >= 0.9 * len(existing):
        return existing
    if os.name != "nt" or not (RUNTIME / "plugins" / "nnls-chroma.dll").is_file():
        return existing
    active = level > max(1e-9, float(np.max(level)) * 0.04)
    strongest = np.sort(pitch, axis=1)
    tuned = tuning[:, 0] > 0.10 * np.maximum(tuning[:, 1], 1e-9)
    polyphonic = active & tuned & (strongest[:, -1] < 0.68) & (strongest[:, -2] > 0.15)
    if np.sum(polyphonic) < 0.30 * max(1, np.sum(active)):
        return existing
    proposals = _segment_labels(path, beats)
    if proposals is None:
        return existing
    # Broadband noise may contain incidental spectral peaks. An isolated chord
    # estimate in a mostly unpitched recording is not an accompaniment chart.
    if sum(map(bool, proposals)) < 0.40 * len(proposals):
        return existing
    edges = np.clip(np.rint(beats / frame_period).astype(int), 0, len(level))
    counts = np.r_[0, np.cumsum(polyphonic)]
    local_support = np.diff(counts[edges]) / np.maximum(1, np.diff(edges))
    def spans(labels):
        counts = []
        for _, members in groupby(labels):
            length = sum(1 for _ in members)
            counts.extend([length] * length)
        return counts

    result = list(existing)
    for i, (native, candidate, support, old_span, new_span) in enumerate(
        zip(existing, proposals, local_support, spans(existing), spans(proposals))
    ):
        if not candidate or support < 0.16 or native == candidate:
            continue
        # Melody notes in an arpeggio can momentarily look like a chord. A
        # sustained alternative across three beats has stronger temporal support.
        # Retain open fifths: pitch evidence there did not establish a third.
        if not native or (not native.endswith("5") and new_span >= 3 and (new_span > old_span or new_span >= 4)):
            result[i] = candidate
    return result
