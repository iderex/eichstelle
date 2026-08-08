"""The noise a description actually produces, measured rather than assumed.

Two claims are checked here that cannot be checked in process or in a hurry.

That the samples are identical across separate invocations of the interpreter.
A generator can be reproducible inside one process and not across two: a hash
seeded per process, an iteration order, a cached table built from something that
moves. The only way to know is to start the interpreter twice.

That the spectrum of the rendered signal is the spectrum the description asked
for. The unit suite checks the filter's designed response against the Butterworth
formula, which says the design is right. This says the design reached the
samples, which is a different claim and the one a fixture rests on.

The spectra are measured against a white signal drawn from the SAME seed, so both
signals carry one realisation of one noise and the ratio of their spectra is the
filter rather than the luck of the draw.
"""

import hashlib
import math
import subprocess
import sys
from typing import Any

from eichstelle.signals import parse_noise, render_noise
from eichstelle.signals.noise import _butterworth_bandpass, _cascade_magnitude

SAMPLE_RATE = 48000
LOW_EDGE = 920.0
HIGH_EDGE = 1080.0
ORDER = 4
SEED = 20260808

# Long enough that the measurement below has segments to average, short enough
# that rendering it in pure Python is not the slowest thing in the suite.
MEASUREMENT_SECONDS = "4.0"

# The measurement. A Hann window, segments overlapping by half, and the discrete
# transform evaluated at the frequencies of interest rather than at every bin,
# because only a dozen frequencies are wanted and a full transform in pure
# Python would cost far more for the rest.
SEGMENT = 4096
SETTLE = 4096
SEGMENTS = 40


def description(kind: str, **parameters: Any) -> dict[str, Any]:
    """A noise description with no fade, so the whole signal is stationary."""
    return {
        "kind": kind,
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "duration_seconds": MEASUREMENT_SECONDS,
        "parameters": {
            "random_algorithm": "xoshiro256plusplus",
            "random_seed": SEED,
            "level_db_spl": "60.0",
            "calibration_reference_db_spl": "94.0",
            "fade": {"shape": "none", "duration_seconds": "0.0"},
            **parameters,
        },
    }


def band_power(block: list[float], frequency: float) -> float:
    """The squared magnitude of the transform at one frequency, by Goertzel."""
    angle = 2 * math.pi * frequency / SAMPLE_RATE
    coefficient = 2 * math.cos(angle)
    previous = 0.0
    older = 0.0
    for value in block:
        current = value + coefficient * previous - older
        older = previous
        previous = current
    real = previous - older * math.cos(angle)
    imaginary = older * math.sin(angle)
    return real * real + imaginary * imaginary


def spectrum(samples: list[float], frequencies: list[float]) -> dict[float, float]:
    """Averaged periodogram values at the frequencies asked for.

    The first `SETTLE` samples are dropped, so what is measured is the filter's
    steady state rather than its start-up transient.
    """
    data = samples[SETTLE:]
    window = [
        0.5 - 0.5 * math.cos(2 * math.pi * index / SEGMENT) for index in range(SEGMENT)
    ]
    totals = dict.fromkeys(frequencies, 0.0)
    taken = 0
    position = 0
    while position + SEGMENT <= len(data) and taken < SEGMENTS:
        block = [data[position + index] * window[index] for index in range(SEGMENT)]
        for frequency in frequencies:
            totals[frequency] += band_power(block, frequency)
        taken += 1
        position += SEGMENT // 2
    assert taken == SEGMENTS, f"only {taken} segments were available"
    return {frequency: totals[frequency] / taken for frequency in frequencies}


RENDER_AND_HASH = """
import hashlib, json, sys
from eichstelle.signals import parse_noise, render_noise
description = json.loads(sys.argv[1])
samples = render_noise(parse_noise(description))
digest = hashlib.sha256()
for value in samples:
    digest.update(value.hex().encode("ascii"))
sys.stdout.write(digest.hexdigest())
"""


def hash_in_this_process(document: dict[str, Any]) -> str:
    """The same digest as the subprocess computes, from the same samples."""
    digest = hashlib.sha256()
    for value in render_noise(parse_noise(document)):
        digest.update(value.hex().encode("ascii"))
    return digest.hexdigest()


def hash_in_a_new_process(document: dict[str, Any]) -> str:
    """Render the description in a fresh interpreter and hash what came out."""
    import json

    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", RENDER_AND_HASH, json.dumps(document)],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_two_separate_interpreters_produce_the_same_samples() -> None:
    """The claim a noise fixture rests on, checked the only way it can be.

    The digest covers every sample's exact bits, through `float.hex`, so two
    signals differing in the last place of one sample fail this.
    """
    document = description("noise", spectral_shape="pink")
    first = hash_in_a_new_process(document)
    second = hash_in_a_new_process(document)

    assert first == second
    assert first == hash_in_this_process(document)


def test_a_band_limited_signal_carries_the_response_it_declared() -> None:
    """The rendered spectrum against the filter the description named.

    Compared as a shape rather than as a level: the generator scales both
    signals to the same level, so the ratio of their spectra carries a constant
    offset which is removed by referring everything to the centre frequency.

    The bound is 1 dB. The worst deviation when this was written is 0.43 dB, and
    the response of a neighbouring filter is nowhere near inside it: at 1500 Hz
    an order of 4 is 57.6 dB down and an order of 3 is 43.2 dB down, so an order
    off by one fails this by more than 14 dB.
    """
    white = render_noise(parse_noise(description("noise", spectral_shape="white")))
    banded = render_noise(
        parse_noise(
            description(
                "band_limited_noise",
                low_edge_hz=str(LOW_EDGE),
                high_edge_hz=str(HIGH_EDGE),
                filter_type="butterworth",
                filter_order=ORDER,
            )
        )
    )

    frequencies = [500.0, 700.0, 850.0, 920.0, 1000.0, 1080.0, 1200.0, 1500.0, 2000.0]
    flat = spectrum(white, frequencies)
    shaped = spectrum(banded, frequencies)
    sections, gain = _butterworth_bandpass(LOW_EDGE, HIGH_EDGE, ORDER, SAMPLE_RATE)

    def measured(frequency: float) -> float:
        return 10 * math.log10(shaped[frequency] / flat[frequency])

    def designed(frequency: float) -> float:
        return 20 * math.log10(
            _cascade_magnitude(sections, gain, frequency, SAMPLE_RATE)
        )

    for frequency in frequencies:
        difference = (measured(frequency) - measured(1000.0)) - (
            designed(frequency) - designed(1000.0)
        )
        assert abs(difference) < 1.0, (
            f"at {frequency:.0f} Hz the produced signal is {difference:+.3f} dB "
            f"from the response the description declared"
        )


def test_pink_noise_falls_at_three_decibels_per_octave() -> None:
    """The produced signal, not the ladder's coefficients.

    The bound is 1 dB and it covers two things at once: the ladder is an
    approximation, which the unit suite bounds at 0.6 dB over its declared span,
    and a measured spectrum of a finite noise has a spread of its own. The worst
    deviation when this was written is 0.41 dB, at 8 kHz.
    """
    white = render_noise(parse_noise(description("noise", spectral_shape="white")))
    pink = render_noise(parse_noise(description("noise", spectral_shape="pink")))

    frequencies = [125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0]
    flat = spectrum(white, frequencies)
    shaped = spectrum(pink, frequencies)
    reference = 10 * math.log10(shaped[1000.0] / flat[1000.0])

    for frequency in frequencies:
        measured = 10 * math.log10(shaped[frequency] / flat[frequency]) - reference
        ideal = -3.0102999566 * math.log2(frequency / 1000.0)
        assert abs(measured - ideal) < 1.0, (
            f"at {frequency:.0f} Hz the produced pink noise is "
            f"{measured - ideal:+.3f} dB from the slope it declares"
        )


def test_white_noise_is_flat() -> None:
    """The shape that is easiest to assume and worth measuring anyway.

    A generator whose stream was correlated, or whose Gaussian transform was
    wrong, would show as a tilt or a bump here. The bound is 1.5 dB, against a
    worst departure of 0.53 dB when this was written; averaging forty segments
    leaves a spread of roughly this size in a measurement of noise, which is why
    it is not tighter.
    """
    white = render_noise(parse_noise(description("noise", spectral_shape="white")))
    frequencies = [125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0]
    flat = spectrum(white, frequencies)

    levels = [10 * math.log10(flat[frequency]) for frequency in frequencies]
    mean = sum(levels) / len(levels)
    for frequency, level in zip(frequencies, levels, strict=True):
        assert abs(level - mean) < 1.5, (
            f"at {frequency:.0f} Hz white noise sits {level - mean:+.3f} dB from "
            f"its own mean across the band"
        )
