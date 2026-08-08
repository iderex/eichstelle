"""What the modulated generators produce, measured from the samples.

The depth and the level are the two things a fixture author can get wrong here
without noticing, and both are measured from the produced signal rather than
recomputed the way the generator computed them.

The level convention is the expensive one. At full depth the two readings of a
level differ by 1.760913 dB, and a fixture set built under the wrong reading
reports every implementation as disagreeing by that much, in the same direction,
on exactly the fixtures the roughness and fluctuation strength anchors rest on.
So both readings are produced here and the difference between them is asserted
against the closed form in `docs/calibration.md`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest

from eichstelle.signals import (
    DEFAULT_PHASE,
    DescriptionError,
    encode_pcm,
    parse_modulated,
    render_modulated,
)

# 1000 Hz at 48000 Hz is 48 samples per period, so the carrier is exactly plus
# or minus one at samples 12, 36, 60 and every 24 after that. At 200 Hz the
# envelope reaches its extremes at samples 60 and 180 and every 240 after them,
# and both of those are on the carrier grid, so the magnitude there is the
# carrier amplitude times one plus or minus the depth with nothing
# approximated. That alignment is what makes the exact depth measurement below
# possible; it was chosen for it rather than found by luck.
AM: Mapping[str, Any] = {
    "kind": "amplitude_modulated_sinusoid",
    "sample_rate": 48000,
    "channels": 1,
    "duration_seconds": "1.0",
    "bit_depth": 16,
    "parameters": {
        "carrier_frequency_hz": "1000.0",
        "modulation_frequency_hz": "200.0",
        "modulation_depth": "1.0",
        "level_db_spl": "60.0",
        "level_convention": "carrier",
        "calibration_reference_db_spl": "94.0",
        "fade": {"shape": "none", "duration_seconds": "0"},
    },
}

FM: Mapping[str, Any] = {
    "kind": "frequency_modulated_sinusoid",
    "sample_rate": 48000,
    "channels": 1,
    "duration_seconds": "1.0",
    "bit_depth": 16,
    "parameters": {
        "carrier_frequency_hz": "1000.0",
        "modulation_frequency_hz": "4.0",
        "frequency_deviation_hz": "100.0",
        "level_db_spl": "60.0",
        "level_convention": "carrier",
        "calibration_reference_db_spl": "94.0",
        "fade": {"shape": "none", "duration_seconds": "0"},
    },
}


def amended(base: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    """A copy of a description with parameter keys replaced, or removed."""
    out: dict[str, Any] = {**base, "parameters": dict(base["parameters"])}
    for key, value in changes.items():
        if value is None:
            out["parameters"].pop(key, None)
        else:
            out["parameters"][key] = value
    return out


def root_mean_square(values: list[float]) -> float:
    """Summed with math.fsum, so the summation contributes no error of its own."""
    return math.sqrt(math.fsum(value * value for value in values) / len(values))


def level_of(values: list[float], reference_db_spl: float = 94.0) -> float:
    """The sound pressure level a run of samples carries."""
    return reference_db_spl + 20 * math.log10(root_mean_square(values) * math.sqrt(2))


def carrier_peaks(samples: list[float]) -> list[float]:
    """The magnitude at every sample where the 1 kHz carrier is exactly one.

    Those samples carry the envelope and nothing else, so a maximum and a
    minimum over them are the envelope's own extremes rather than an estimate
    taken from a window.
    """
    return [abs(samples[index]) for index in range(12, len(samples), 24)]


def measured_depth(samples: list[float]) -> float:
    """The modulation depth, read off the envelope.

    The envelope runs between one plus and one minus the depth, so the
    difference over the sum of its extremes is the depth with the carrier
    amplitude cancelled out. Nothing about the requested depth enters here.
    """
    peaks = carrier_peaks(samples)
    high, low = max(peaks), min(peaks)
    return (high - low) / (high + low)


def instantaneous_frequencies(samples: list[float], sample_rate: int) -> list[float]:
    """The frequency between consecutive upward zero crossings.

    The crossing is interpolated linearly between the two samples that straddle
    it, so the estimate is not quantised to the sample grid.
    """
    crossings: list[float] = []
    for index in range(len(samples) - 1):
        here, then = samples[index], samples[index + 1]
        if here <= 0 < then:
            crossings.append(index + (-here) / (then - here))
    return [
        sample_rate / (crossings[index + 1] - crossings[index])
        for index in range(len(crossings) - 1)
    ]


# ---------------------------------------------------------------------------
# The modulation depth, measured from the samples
# ---------------------------------------------------------------------------


def test_the_measured_depth_is_exact_on_the_aligned_grid() -> None:
    """At full depth on a grid where the envelope extremes land on carrier peaks.

    Nothing is approximated: the samples read are ones where the carrier is
    exactly one, and the envelope reaches exactly one plus and one minus the
    depth at two of them. The bound is a billionth, which is float headroom
    rather than a measurement tolerance.
    """
    samples = render_modulated(parse_modulated(AM))

    assert abs(measured_depth(samples) - 1.0) < 1e-9


@pytest.mark.parametrize("depth", ["1.0", "0.5", "0.25"])
def test_the_measured_depth_is_the_requested_depth(depth: str) -> None:
    """Three depths, each read back off the envelope."""
    samples = render_modulated(parse_modulated(amended(AM, modulation_depth=depth)))

    assert abs(measured_depth(samples) - float(depth)) < 1e-9


def test_the_measured_depth_at_the_roughness_anchor() -> None:
    """70 Hz, which is the anchor and is not on the aligned grid.

    The carrier peaks are 0.5 ms apart and the envelope moves at 70 Hz, so the
    largest and smallest of them sit slightly inside the envelope's true
    extremes. The worst case for a single period is a factor of
    cos(2 * pi * 70 * 0.00025), which is 0.6 percent low; over a second the
    sampling phase drifts across the envelope and the observed error is far
    smaller. The bound of a thousandth is between the two and is a ceiling
    rather than the measured number, which is 1.2e-4.
    """
    samples = render_modulated(
        parse_modulated(amended(AM, modulation_frequency_hz="70.0"))
    )

    assert abs(measured_depth(samples) - 1.0) < 1e-3


# ---------------------------------------------------------------------------
# The level, under each convention
# ---------------------------------------------------------------------------


def test_the_two_level_conventions_differ_by_the_closed_form() -> None:
    """Both readings are produced and they differ by 10 * log10(1 + m ** 2 / 2).

    This is the assertion the issue exists for. Under the carrier reading the
    produced signal is louder than the level it states, by exactly the amount
    `docs/calibration.md` derives. Under the modulated reading the produced
    signal carries the level it states. A generator that ignored the field would
    make these two equal and this test would go red.
    """
    carrier = render_modulated(parse_modulated(amended(AM, level_convention="carrier")))
    modulated = render_modulated(
        parse_modulated(amended(AM, level_convention="modulated"))
    )

    difference = level_of(carrier) - level_of(modulated)
    closed_form = 10 * math.log10(1 + 1.0**2 / 2)

    assert abs(closed_form - 1.760913) < 1e-6
    assert abs(difference - closed_form) < 1e-9


def test_under_the_modulated_reading_the_produced_signal_carries_the_level() -> None:
    """Measured over the whole signal, which is what that reading names."""
    signal = parse_modulated(amended(AM, level_convention="modulated"))
    samples = render_modulated(signal)

    assert abs(level_of(samples) - 60.0) < 1e-9


def test_under_the_carrier_reading_the_unmodulated_carrier_carries_the_level() -> None:
    """The carrier amplitude is what the level maps to, envelope aside.

    Read from the samples where the carrier is exactly one and the envelope is
    exactly one, which are the crossings of the modulator. At 200 Hz the
    modulator is zero at samples 0, 120, 240 and every 120 after that, and 120
    is a multiple of 24, so those instants are on the carrier grid too.
    """
    signal = parse_modulated(amended(AM, level_convention="carrier"))
    samples = render_modulated(signal)

    # Sample 12 is a carrier peak; sample 0 and every 120th are modulator zeros.
    # Their intersection is not a single sample, so the carrier amplitude is
    # read from the envelope extremes instead: their mean is the carrier.
    peaks = carrier_peaks(samples)
    carrier_amplitude = (max(peaks) + min(peaks)) / 2

    assert carrier_amplitude == pytest.approx(10 ** ((60.0 - 94.0) / 20), rel=1e-12)


def test_a_frequency_modulated_signal_reads_the_same_under_both_conventions() -> None:
    """Its envelope is constant, so there is nothing for the readings to differ on.

    The field is still required on it, which the refusal below asserts. This is
    the fact a reader would otherwise have to know in order to read a fixture.
    """
    carrier = render_modulated(parse_modulated(amended(FM, level_convention="carrier")))
    modulated = render_modulated(
        parse_modulated(amended(FM, level_convention="modulated"))
    )

    assert carrier == modulated
    assert abs(level_of(carrier) - 60.0) < 1e-9


# ---------------------------------------------------------------------------
# Frequency modulation
# ---------------------------------------------------------------------------


def test_the_measured_deviation_is_the_requested_deviation() -> None:
    """The instantaneous frequency sweeps between the carrier plus and minus it.

    Measured between interpolated upward zero crossings, which gives the mean
    frequency over one carrier period rather than the instantaneous one. Two
    effects put the reading slightly inside the true extremes: that averaging,
    which costs a factor of sinc(pi * fm / fc) and is 2.6e-3 Hz here, and the
    crossings landing near rather than on the extremes of a 4 Hz sweep, which is
    at most 100 * (1 - cos(2 * pi * 4 * 0.0005)) and is 7.9e-3 Hz. The bound of
    0.05 Hz is about five times the larger of the two; the measured errors are
    0.010 Hz and 0.003 Hz.
    """
    signal = parse_modulated(FM)
    frequencies = instantaneous_frequencies(render_modulated(signal), 48000)

    assert len(frequencies) > 900
    assert abs(min(frequencies) - 900.0) < 0.05
    assert abs(max(frequencies) - 1100.0) < 0.05


def test_a_frequency_modulated_signal_has_a_constant_envelope() -> None:
    """Which is why the two level readings coincide on it.

    The peak of the produced signal is the carrier amplitude, not more, and the
    samples reach it because a 4 Hz sweep of a 1 kHz carrier crosses its own
    peak a thousand times in a second.
    """
    signal = parse_modulated(FM)
    samples = render_modulated(signal)

    assert max(abs(value) for value in samples) == pytest.approx(
        signal.carrier_amplitude, rel=1e-6
    )


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------


def test_the_initial_phases_default_to_zero_and_are_stated() -> None:
    """A description that says nothing about phase has still named one."""
    signal = parse_modulated(AM)

    assert DEFAULT_PHASE == 0.0
    assert signal.carrier_phase_radians == 0.0
    assert signal.modulator_phase_radians == 0.0


def test_a_stated_carrier_phase_moves_the_carrier() -> None:
    """A quarter turn puts the carrier at its peak on the first sample.

    The envelope at sample zero is one, because the modulator starts at zero,
    so the first sample is the carrier amplitude exactly.
    """
    signal = parse_modulated(
        amended(AM, carrier_phase_radians=str(math.pi / 2), level_convention="carrier")
    )
    samples = render_modulated(signal)

    assert samples[0] == pytest.approx(signal.carrier_amplitude, rel=1e-12)


def test_a_stated_modulator_phase_moves_the_envelope() -> None:
    """A quarter turn starts the envelope at its maximum instead of its middle.

    Read at the first carrier peak rather than at sample zero, because the
    carrier itself is zero there.
    """
    plain = render_modulated(parse_modulated(AM))
    shifted = render_modulated(
        parse_modulated(amended(AM, modulator_phase_radians=str(math.pi / 2)))
    )

    assert abs(shifted[12]) > abs(plain[12])


# ---------------------------------------------------------------------------
# The anchors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("modulation_frequency_hz", "what"),
    [("70.0", "one asper"), ("4.0", "one vacil")],
)
def test_the_reference_anchors_render(modulation_frequency_hz: str, what: str) -> None:
    """One asper and one vacil are definitions rather than measurements.

    Both are a 1 kHz carrier at 60 dB SPL modulated at full depth, at 70 Hz and
    at 4 Hz. `docs/calibration.md` states them under the carrier reading, and
    what is asserted here is that this generator produces exactly that from a
    description saying so, at full depth and at the stated level.
    """
    signal = parse_modulated(
        amended(
            AM,
            modulation_frequency_hz=modulation_frequency_hz,
            modulation_depth="1.0",
            level_convention="carrier",
        )
    )
    samples = render_modulated(signal)

    assert what in ("one asper", "one vacil")
    assert signal.carrier_amplitude == pytest.approx(
        10 ** ((60.0 - 94.0) / 20), rel=1e-12
    )
    assert abs(measured_depth(samples) - 1.0) < 1e-3


# ---------------------------------------------------------------------------
# Repeatability and encoding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("description", [AM, FM])
def test_generating_the_same_description_twice_is_byte_identical(
    description: Mapping[str, Any],
) -> None:
    """Two renders of one description produce the same bytes."""
    first = encode_pcm(render_modulated(parse_modulated(description)), 16)
    second = encode_pcm(render_modulated(parse_modulated(description)), 16)

    assert first == second
    assert len(first) == 2 * 48000


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("description", [AM, FM])
def test_a_description_with_no_level_convention_is_refused(
    description: Mapping[str, Any],
) -> None:
    """On both kinds, including the one where the two readings coincide.

    Matched on the sentence this refusal alone carries rather than on the field
    name, because the generic missing-field message names the field too and a
    test matching only that would pass with this refusal deleted.
    """
    with pytest.raises(DescriptionError, match="has no default for it"):
        parse_modulated(amended(description, level_convention=None))


def test_a_description_with_no_calibration_reference_is_refused() -> None:
    """The same refusal the unmodulated generator makes, for the same reason."""
    with pytest.raises(DescriptionError, match="full-scale"):
        parse_modulated(amended(AM, calibration_reference_db_spl=None))


@pytest.mark.parametrize(
    ("description", "message"),
    [
        (amended(AM, level_convention="peak"), "is not one this generator reads"),
        (amended(AM, modulation_depth="1.5"), "inverts the carrier"),
        (amended(AM, modulation_depth="-0.1"), "inverts the carrier"),
        (amended(AM, modulation_depth=None), "no modulation_depth"),
        (amended(AM, level_db_spl="93.0"), "would clip"),
        (amended(AM, modulation_frequency_hz="0.0"), "modulation_frequency_hz is 0"),
        (amended(AM, carrier_frequency_hz="30000.0"), "half the sample rate"),
        (amended(FM, frequency_deviation_hz=None), "no frequency_deviation_hz"),
        (amended(FM, frequency_deviation_hz="1000.0"), "to or below"),
        # A deviation smaller than the carrier, so the sweep stays positive and
        # the other refusal does not fire first, but large enough that the top
        # of the sweep passes half the sample rate.
        (
            amended(
                FM, carrier_frequency_hz="20000.0", frequency_deviation_hz="5000.0"
            ),
            "would alias",
        ),
    ],
)
def test_a_modulated_description_the_generator_cannot_render_is_refused(
    description: Mapping[str, Any], message: str
) -> None:
    """Each refusal names the field, so a fixture author knows what to fix."""
    with pytest.raises(DescriptionError, match=message):
        parse_modulated(description)


def test_a_level_that_fits_an_unmodulated_tone_can_still_clip_when_modulated() -> None:
    """The peak is the carrier times one plus the depth, and that is the trap.

    93.0 dB against a 94.0 dB reference is a carrier peak of 0.891, which is
    inside full scale. At full depth the envelope takes it to 1.783, which is
    not, and the refusal says so rather than producing a saturated signal that
    every implementation would then disagree about.
    """
    assert 10 ** ((93.0 - 94.0) / 20) < 1.0
    assert 10 ** ((93.0 - 94.0) / 20) * 2 > 1.0

    with pytest.raises(DescriptionError, match="can still clip once it is modulated"):
        parse_modulated(amended(AM, level_db_spl="93.0"))


def test_the_unmodulated_kind_is_refused_by_the_modulated_parser() -> None:
    """Each parser reads its own kinds and says which ones those are."""
    plain = {**AM, "kind": "sinusoid"}

    with pytest.raises(DescriptionError, match="this generator renders"):
        parse_modulated(plain)
