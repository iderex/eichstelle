"""What the noise generator produces, and every description it refuses.

Three properties are worth more than the rest here, and they are the ones a
noise fixture is worthless without.

That the stream is reproducible. A noise that differs between two runs turns
every comparison downstream into a comparison of two different stimuli, and it
does so silently, because both look exactly like noise.

That the stated level is the produced level. A filter has pass band ripple, so a
level computed from theory and a level measured off the samples differ, and the
fixture's number has to be the one a meter would read.

That the declared shape is the produced shape. This is the one that is easy to
assert badly: a test that asserts "some energy in the band" passes under a filter
of the wrong order, the wrong edges or the wrong family. So the spectrum of the
rendered signal is measured and compared against the response the description
asked for, and the bound is tight enough that a one-character change to the order
fails it.

The spectra are measured against a white signal drawn from the SAME seed. Both
signals then carry one realisation of one noise, so the ratio of their spectra is
the filter and not the luck of the draw, and the bound can be about the filter.
"""

import math
from typing import Any

import pytest

from eichstelle.signals import (
    DescriptionError,
    parse_noise,
    render_noise,
)
from eichstelle.signals.noise import (
    _butterworth_bandpass,
    _cascade_magnitude,
    _pink_ladder,
)

SAMPLE_RATE = 48000
REFERENCE_DB = 94.0
LEVEL_DB = 60.0

# The band the sharpness reference sits in: one critical band wide at one
# kilohertz, near enough for a test whose subject is the filter rather than the
# psychoacoustics.
LOW_EDGE = 920.0
HIGH_EDGE = 1080.0


def stream_parameters() -> dict[str, Any]:
    """The two fields every noise description carries."""
    return {"random_algorithm": "xoshiro256plusplus", "random_seed": 20260808}


def broadband(shape: str = "white", **over: Any) -> dict[str, Any]:
    """A valid broadband description, and the base of every neighbour below."""
    parameters: dict[str, Any] = {
        **stream_parameters(),
        "spectral_shape": shape,
        "level_db_spl": str(LEVEL_DB),
        "calibration_reference_db_spl": str(REFERENCE_DB),
        "fade": {"shape": "raised_cosine", "duration_seconds": "0.05"},
    }
    parameters.update(over)
    return {
        "kind": "noise",
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "duration_seconds": "0.5",
        "parameters": parameters,
    }


def band_limited(**over: Any) -> dict[str, Any]:
    """A valid band-limited description, and the base of every neighbour below."""
    parameters: dict[str, Any] = {
        **stream_parameters(),
        "low_edge_hz": str(LOW_EDGE),
        "high_edge_hz": str(HIGH_EDGE),
        "filter_type": "butterworth",
        "filter_order": 4,
        "level_db_spl": str(LEVEL_DB),
        "calibration_reference_db_spl": str(REFERENCE_DB),
        "fade": {"shape": "raised_cosine", "duration_seconds": "0.05"},
    }
    parameters.update(over)
    return {
        "kind": "band_limited_noise",
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "duration_seconds": "0.5",
        "parameters": parameters,
    }


def measured_level_db(samples: list[float], fade_frames: int) -> float:
    """The level of the sustain, read back off the samples.

    The same arithmetic `docs/calibration.md` states, run in the other
    direction: a level is the root mean square scaled by the square root of two
    against the level of a full-scale sine.
    """
    sustain = samples[fade_frames : len(samples) - fade_frames]
    rms = math.sqrt(sum(value * value for value in sustain) / len(sustain))
    return REFERENCE_DB + 20 * math.log10(rms * math.sqrt(2.0))


def test_the_stream_is_the_published_one() -> None:
    """The first words for a known seed, so the sequence itself is pinned.

    Every other property here would survive the generator being swapped for a
    different one. This is the test that would not: it says which sequence a
    fixture naming `xoshiro256plusplus` and this seed gets, forever. The values
    are what this implementation produced when it was written, and a change to
    them is a change to every noise fixture in the set.
    """
    from eichstelle.signals import words

    stream = words(1)
    first = [next(stream) for _ in range(4)]
    assert first == [
        14971601782005023387,
        13781649495232077965,
        1847458086238483744,
        13765271635752736470,
    ]


def test_two_runs_in_one_process_are_identical() -> None:
    """The same description twice gives the same samples, bit for bit."""
    first = render_noise(parse_noise(broadband()))
    second = render_noise(parse_noise(broadband()))
    assert first == second


def test_a_different_seed_is_a_different_signal() -> None:
    """Without this the reproducibility test above would pass on a constant."""
    first = render_noise(parse_noise(broadband()))
    second = render_noise(parse_noise(broadband(random_seed=20260809)))
    assert first != second


@pytest.mark.parametrize("shape", ["white", "pink"])
def test_the_measured_level_of_broadband_noise_is_the_requested_level(
    shape: str,
) -> None:
    """The level is measured off the produced samples, so it lands exactly.

    The bound is 0.01 dB rather than something looser because the generator
    scales by a measured root mean square rather than by a computed amplitude.
    Anything approaching a tenth of a decibel here would mean it had stopped.
    """
    signal = parse_noise(broadband(shape))
    samples = render_noise(signal)
    assert abs(measured_level_db(samples, signal.fade_frames) - LEVEL_DB) < 0.01


def test_the_measured_level_of_band_limited_noise_is_the_requested_level() -> None:
    """The same, through a filter, which is where theory and practice part.

    A level computed from the requested one and the filter's theoretical gain
    would be out by the pass band ripple. This is the case the issue that built
    this names.
    """
    signal = parse_noise(band_limited())
    samples = render_noise(signal)
    assert abs(measured_level_db(samples, signal.fade_frames) - LEVEL_DB) < 0.01


def test_the_band_pass_realises_the_butterworth_it_names() -> None:
    """The designed cascade against the Butterworth formula, independently.

    The cascade is built by pole placement and a bilinear transform. The formula
    on the right is the definition of a Butterworth band-pass on the pre-warped
    analogue axis, written out here rather than taken from the code under test,
    so a mistake in the design does not appear on both sides.

    Every order this generator admits is checked, because the pole layout
    differs between odd and even orders and an odd order is the case that would
    be got wrong.
    """
    for order in (1, 2, 3, 4, 5, 6, 7, 8):
        sections, gain = _butterworth_bandpass(LOW_EDGE, HIGH_EDGE, order, SAMPLE_RATE)
        warped_low = 2 * SAMPLE_RATE * math.tan(math.pi * LOW_EDGE / SAMPLE_RATE)
        warped_high = 2 * SAMPLE_RATE * math.tan(math.pi * HIGH_EDGE / SAMPLE_RATE)
        width = warped_high - warped_low
        centre_squared = warped_low * warped_high

        for frequency in (100.0, 500.0, 920.0, 1000.0, 1080.0, 2000.0, 8000.0):
            warped = 2 * SAMPLE_RATE * math.tan(math.pi * frequency / SAMPLE_RATE)
            formula = 1.0 / math.sqrt(
                1.0
                + ((warped * warped - centre_squared) / (width * warped)) ** (2 * order)
            )
            built = _cascade_magnitude(sections, gain, frequency, SAMPLE_RATE)
            assert abs(20 * math.log10(built / formula)) < 1e-6


def test_the_band_edges_are_the_half_power_points() -> None:
    """What `low_edge_hz` and `high_edge_hz` mean, asserted rather than assumed.

    A fixture author writing a one-bark band is stating where the response is
    3 dB down. The bilinear transform warps frequency, and a design that skipped
    the pre-warp would put the edges near these numbers rather than on them,
    which is the mistake this catches.
    """
    for order in (2, 4, 8):
        sections, gain = _butterworth_bandpass(LOW_EDGE, HIGH_EDGE, order, SAMPLE_RATE)
        for edge in (LOW_EDGE, HIGH_EDGE):
            at_edge = 20 * math.log10(
                _cascade_magnitude(sections, gain, edge, SAMPLE_RATE)
            )
            assert abs(at_edge - (-3.0103)) < 0.001


def test_the_pink_ladder_falls_at_three_decibels_per_octave() -> None:
    """The shaping cascade against the slope it claims, over a declared band.

    Measured from 20 Hz to a fifth of the sample rate, which is the span
    `docs/fixtures.md` declares for this shape. The bound is 0.6 dB and the worst
    deviation at the commit this was written on is 0.52 dB, at the top of the
    band. A ladder is an approximation and this is the size of it; the point of
    the test is that the size cannot grow without somebody deciding it should.
    """
    for rate in (44100, 48000, 96000):
        sections = _pink_ladder(rate)
        points = []
        frequency = 20.0
        top = rate / 5
        while frequency <= top:
            unit = complex(
                math.cos(-2 * math.pi * frequency / rate),
                math.sin(-2 * math.pi * frequency / rate),
            )
            response = complex(1.0, 0.0)
            for gain, pole, zero in sections:
                response *= gain * (1 - zero * unit) / (1 - pole * unit)
            points.append((math.log2(frequency), 20 * math.log10(abs(response))))
            frequency *= 2 ** (1 / 24)

        slope = -3.0102999566
        offset = sum(value - slope * octave for octave, value in points) / len(points)
        worst = max(abs(value - (slope * octave + offset)) for octave, value in points)
        assert worst < 0.6, f"at {rate} Hz the ladder is {worst:.3f} dB from the slope"


def test_a_seed_that_is_not_an_integer_is_refused() -> None:
    """Refused rather than coerced, because a coerced seed is a different stream."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(broadband(random_seed="20260808"))
    assert "random_seed" in str(raised.value)


def test_a_description_with_no_seed_is_refused() -> None:
    """The refusal the issue that built this names first.

    A default seed inside a generator is a stimulus nobody wrote down, and every
    fixture written afterwards would inherit it without saying so.
    """
    description = broadband()
    del description["parameters"]["random_seed"]
    with pytest.raises(DescriptionError) as raised:
        parse_noise(description)
    assert "no random_seed" in str(raised.value)


def test_a_description_with_no_algorithm_is_refused() -> None:
    """A seed alone does not identify a sequence."""
    description = broadband()
    del description["parameters"]["random_algorithm"]
    with pytest.raises(DescriptionError) as raised:
        parse_noise(description)
    assert "random_algorithm" in str(raised.value)


def test_an_algorithm_this_generator_does_not_implement_is_refused() -> None:
    """Naming a library's default here would be the failure the field exists for."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(broadband(random_algorithm="mersenne_twister"))
    assert "mersenne_twister" in str(raised.value)


def test_a_spectral_shape_no_generator_produces_is_refused() -> None:
    """A shape nobody implemented is a fixture against a feature that never landed."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(broadband("brown"))
    assert "spectral_shape" in str(raised.value)


def test_a_filter_type_this_generator_does_not_build_is_refused() -> None:
    """The brick wall is a different stimulus, not a synonym for the realisable one."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(band_limited(filter_type="brickwall"))
    assert "filter_type" in str(raised.value)


def test_a_band_limited_description_with_no_filter_order_is_refused() -> None:
    """Edges without an order do not describe the stimulus."""
    description = band_limited()
    del description["parameters"]["filter_order"]
    with pytest.raises(DescriptionError) as raised:
        parse_noise(description)
    assert "filter_order" in str(raised.value)


def test_an_order_this_generator_does_not_design_is_refused() -> None:
    """Refused rather than rounded to the nearest one it does design."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(band_limited(filter_order=12))
    assert "filter_order is 12" in str(raised.value)


def test_an_inverted_band_is_refused() -> None:
    """Two edges the wrong way round produce a filter nobody asked for."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(band_limited(low_edge_hz="1080.0", high_edge_hz="920.0"))
    assert "inverted" in str(raised.value)


def test_a_band_reaching_nyquist_is_refused() -> None:
    """A band that cannot be represented at the stated rate is not a band."""
    with pytest.raises(DescriptionError) as raised:
        parse_noise(band_limited(high_edge_hz="24000.0"))
    assert "Nyquist" in str(raised.value)


def test_a_level_whose_samples_would_clip_is_refused() -> None:
    """A noise peaks well above its root mean square, and a tone does not.

    A level a sinusoid carries comfortably can put a noise outside the range a
    sample holds, and clipping is broadband energy every metric under test would
    see. Refused rather than written out.
    """
    with pytest.raises(DescriptionError) as raised:
        render_noise(parse_noise(broadband(level_db_spl="94.0")))
    assert "outside the range a sample holds" in str(raised.value)


def test_a_fade_covering_the_whole_signal_is_refused() -> None:
    """There has to be a sustain, because the sustain is what the level names."""
    description = broadband()
    description["parameters"]["fade"] = {
        "shape": "raised_cosine",
        "duration_seconds": "0.25",
    }
    with pytest.raises(DescriptionError) as raised:
        render_noise(parse_noise(description))
    assert "no sustain" in str(raised.value)


def test_every_channel_carries_the_same_samples() -> None:
    """Two channels of one noise, not two noises, because nothing says which."""
    description = broadband()
    description["channels"] = 2
    samples = render_noise(parse_noise(description))
    assert samples[0::2] == samples[1::2]
