"""What the sinusoid generator produces, measured from the samples.

The point of every measurement here is that it is taken from the signal rather
than from the parameters that made it. A test that recomputes the amplitude the
same way the generator did and compares the two agrees with the generator about
everything, including about being wrong.

`docs/calibration.md` is what these assertions are held to, and the worked
example in that file appears below with the same numbers, so that a change to
either one shows up as a disagreement rather than as two documents drifting.
"""

from __future__ import annotations

import math
import wave
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from eichstelle.signals import (
    DescriptionError,
    encode_pcm,
    parse_sinusoid,
    render,
    write_wave,
)
from eichstelle.signals.generator import Sinusoid

# A description a test starts from and edits. Written out rather than built by a
# helper, because a reader checking a refusal wants to see the whole thing.
BASE: Mapping[str, Any] = {
    "kind": "sinusoid",
    "sample_rate": 48000,
    "channels": 1,
    "duration_seconds": "1.0",
    "bit_depth": 16,
    "parameters": {
        "frequency_hz": "1000.0",
        "level_db_spl": "60.0",
        "calibration_reference_db_spl": "94.0",
        "fade": {"shape": "raised_cosine", "duration_seconds": "0.02"},
    },
}


def described(**changes: Any) -> dict[str, Any]:
    """A copy of BASE with top-level keys replaced."""
    out: dict[str, Any] = {**BASE, "parameters": dict(BASE["parameters"])}
    out.update(changes)
    return out


def with_parameters(**changes: Any) -> dict[str, Any]:
    """A copy of BASE with parameter keys replaced, or removed when None."""
    out = described()
    for key, value in changes.items():
        if value is None:
            out["parameters"].pop(key, None)
        else:
            out["parameters"][key] = value
    return out


def root_mean_square(values: list[float]) -> float:
    """The root mean square of a sample run."""
    return math.sqrt(sum(value * value for value in values) / len(values))


def level_of(values: list[float], reference_db_spl: float) -> float:
    """The sound pressure level a run of samples carries.

    The inverse of what the generator does: a full-scale sine wave has a peak
    of one, so its root mean square is one over the square root of two, and a
    level is twenty times the base-ten logarithm of the ratio of the two root
    mean squares, added to the reference.
    """
    full_scale_rms = 1.0 / math.sqrt(2)
    return reference_db_spl + 20 * math.log10(root_mean_square(values) / full_scale_rms)


# ---------------------------------------------------------------------------
# The level, measured from the signal
# ---------------------------------------------------------------------------


def test_the_measured_level_over_the_sustain_is_the_requested_level() -> None:
    """The sustain carries the level the description asked for.

    The bound is one hundredth of a decibel. A sinusoid's root mean square over
    a finite window is exact only when the window holds a whole number of half
    periods, and this window does not, so the residual is an edge effect of the
    window rather than an error in the amplitude. The sustain here is 0.96 s of
    a 1 kHz tone, so the residual is far below the bound and the bound is a
    ceiling somebody can reason about rather than the measured number.
    """
    signal = parse_sinusoid(BASE)
    samples = render(signal)
    fade = signal.fade_frames
    sustain = samples[fade : signal.frame_count - fade]

    measured = level_of(sustain, signal.calibration_reference_db_spl)

    assert abs(measured - 60.0) < 0.01, measured


def test_the_measured_level_is_exact_over_a_whole_number_of_half_periods() -> None:
    """With the window's own edge effect removed, the amplitude is exact.

    1000 Hz at 48000 Hz is 48 samples per period, so a sustain that is a whole
    multiple of 24 samples holds a whole number of half periods and the root
    mean square is the peak over the square root of two with nothing left over.
    This is the same measurement as above with the excuse taken away.
    """
    signal = parse_sinusoid(
        with_parameters(fade={"shape": "none", "duration_seconds": "0"})
    )
    samples = render(signal)
    whole = (len(samples) // 24) * 24

    measured = level_of(samples[:whole], signal.calibration_reference_db_spl)

    assert abs(measured - 60.0) < 1e-12, measured


def test_the_level_names_the_tone_and_not_the_faded_signal() -> None:
    """A longer fade lowers the level of the whole signal and not the tone.

    This is the convention the module fixes and it is the one a fixture author
    can get wrong. If the level named the produced signal, the sustain
    amplitude would move when the fade duration moved, which would put a
    different tone in front of an implementation for an unrelated edit.
    """
    short = parse_sinusoid(BASE)
    long_fade = parse_sinusoid(
        with_parameters(fade={"shape": "raised_cosine", "duration_seconds": "0.2"})
    )

    assert short.peak_amplitude == long_fade.peak_amplitude

    whole_short = level_of(render(short), short.calibration_reference_db_spl)
    whole_long = level_of(render(long_fade), long_fade.calibration_reference_db_spl)

    assert whole_long < whole_short < 60.0


def test_the_worked_example_in_the_calibration_document_reproduces() -> None:
    """The numbers in docs/calibration.md, produced by this generator.

    A reference of 94.0 dB SPL and a tone at 60.0 dB SPL give a peak amplitude
    of 0.019952623150 and a sixteen-bit sample of 654. The document states both
    and this is what holds the two together.
    """
    signal = parse_sinusoid(BASE)

    assert f"{signal.peak_amplitude:.12f}" == "0.019952623150"

    peak_frame = encode_pcm([signal.peak_amplitude], 16)

    assert int.from_bytes(peak_frame, "little", signed=True) == 654


# ---------------------------------------------------------------------------
# The fade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", ["linear", "raised_cosine"])
def test_the_first_and_last_samples_are_zero(shape: str) -> None:
    """Both ends reach zero exactly, so the signal starts and stops silently."""
    signal = parse_sinusoid(
        with_parameters(fade={"shape": shape, "duration_seconds": "0.02"})
    )
    samples = render(signal)

    assert samples[0] == 0.0
    assert samples[-1] == 0.0


@pytest.mark.parametrize(
    ("shape", "curve"),
    [
        ("linear", lambda position: position),
        ("raised_cosine", lambda position: 0.5 * (1.0 - math.cos(math.pi * position))),
    ],
)
def test_the_fade_follows_the_declared_shape(shape: str, curve: Any) -> None:
    """The envelope over the onset is the shape the description named.

    Read at the tone's own peaks rather than sample by sample, because a
    sinusoid crosses zero inside the fade and a sample there carries the gain
    and the tone together. 1000 Hz at 48000 Hz puts 48 samples in a period, so
    the sine is exactly plus or minus one at samples 12, 36, 60 and every 24
    after that, and the magnitude at those samples is the gain times the peak
    amplitude with nothing approximated. That is what distinguishes a linear
    ramp from a raised cosine, and the two differ by more than a quarter of the
    peak amplitude a quarter of the way into the fade.
    """
    signal = parse_sinusoid(
        with_parameters(fade={"shape": shape, "duration_seconds": "0.05"})
    )
    samples = render(signal)
    fade = signal.fade_frames
    read = 0

    for index in range(12, fade, 24):
        expected = curve(index / fade) * signal.peak_amplitude
        assert abs(samples[index]) == pytest.approx(expected, abs=1e-15)
        read += 1

    assert read == 100


def test_the_two_shapes_are_not_the_same_envelope() -> None:
    """The distinction the test above rests on is a real one.

    Halfway through the onset a linear ramp is at half gain and a raised cosine
    is at half gain too, so the midpoint is where the two agree. A quarter of
    the way in they do not, and that is what is asserted here rather than a
    difference somewhere unnamed.
    """
    quarter_linear = 0.25
    quarter_raised = 0.5 * (1.0 - math.cos(math.pi * 0.25))

    assert abs(quarter_raised - quarter_linear) > 0.1


def test_shape_none_applies_no_shaping() -> None:
    """An unshaped tone is the tone, which is why it can end on a click."""
    signal = parse_sinusoid(
        with_parameters(fade={"shape": "none", "duration_seconds": "0"})
    )
    samples = render(signal)

    assert signal.fade_frames == 0
    assert max(abs(value) for value in samples) == pytest.approx(
        signal.peak_amplitude, rel=1e-6
    )


# ---------------------------------------------------------------------------
# Exact length, exact rate, and repeatability
# ---------------------------------------------------------------------------


def test_the_signal_has_the_length_and_the_rate_the_description_states() -> None:
    """Two of the standards in scope require particular rates.

    A resampled signal is a different signal, so the count of samples and the
    rate written into the container are the description's and not the nearest
    convenient thing.
    """
    signal = parse_sinusoid(described(sample_rate=44100, duration_seconds="0.5"))
    samples = render(signal)

    assert signal.sample_rate == 44100
    assert len(samples) == 22050
    assert signal.frame_count == 22050


def test_a_duration_that_lands_between_two_samples_rounds_rather_than_truncates() -> (
    None
):
    """0.35 s at 44100 Hz is 15434.999999999998 samples in binary floating point.

    Truncating gives 15434 and a reader who multiplied 0.35 by 44100 on paper
    counted 15435. The count matters because issue #25 hashes the samples, so a
    signal one sample shorter than the fixture describes is a different
    stimulus carrying the same description.

    The first assertion is the premise. Most durations do not land here at all,
    and this pair was picked by searching for one that does rather than assumed.
    """
    assert 0.35 * 44100 < 15435

    signal = parse_sinusoid(described(sample_rate=44100, duration_seconds="0.35"))

    assert signal.frame_count == 15435
    assert len(render(signal)) == 15435


def test_every_channel_carries_the_same_tone_interleaved() -> None:
    """Two channels double the sample count and repeat each frame."""
    signal = parse_sinusoid(described(channels=2))
    samples = render(signal)

    assert len(samples) == 2 * signal.frame_count
    assert samples[0::2] == samples[1::2]


def test_generating_the_same_description_twice_is_byte_identical() -> None:
    """Two renders of one description produce the same bytes.

    Asserted on the encoded frames rather than on the floats, because bytes are
    what a checksum in issue #25 will cover and what a second machine will
    compare against.
    """
    first = encode_pcm(render(parse_sinusoid(BASE)), 16)
    second = encode_pcm(render(parse_sinusoid(BASE)), 16)

    assert first == second
    assert len(first) == 2 * 48000


def test_the_written_file_reads_back_with_the_stated_format(tmp_path: Path) -> None:
    """A WAVE file carries the rate, the depth and the channel count stated.

    Everything this test writes is under tmp_path. Nothing in this change reads
    or writes a file anywhere else, and issue #6 forbids one arriving in the
    tree at all.
    """
    signal = parse_sinusoid(described(channels=2, duration_seconds="0.1"))
    written = write_wave(tmp_path / "tone.wav", signal)

    with wave.open(str(written), "rb") as handle:
        assert handle.getnchannels() == 2
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 48000
        assert handle.getnframes() == 4800
        frames = handle.readframes(handle.getnframes())

    assert frames == encode_pcm(render(signal), 16)


def test_a_description_with_no_bit_depth_is_not_written_as_a_wave(
    tmp_path: Path,
) -> None:
    """A float WAVE is a different format and is refused rather than guessed."""
    description = described()
    description.pop("bit_depth")
    signal = parse_sinusoid(description)

    assert signal.bit_depth is None
    with pytest.raises(DescriptionError, match="no bit_depth"):
        write_wave(tmp_path / "tone.wav", signal)


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


def test_a_description_with_no_calibration_reference_is_refused() -> None:
    """The refusal this issue names first.

    A generator that supplied a reference would put a convention nobody wrote
    down behind every fixture that forgot to state one, and the error would be
    a constant offset on all of them at once.

    Matched on the sentence the refusal carries and not on the field name. The
    generic missing-field message names the field too, so a test matching only
    that would pass with this refusal deleted, which was measured rather than
    supposed.
    """
    with pytest.raises(DescriptionError, match="has no default for it"):
        parse_sinusoid(with_parameters(calibration_reference_db_spl=None))


@pytest.mark.parametrize(
    ("description", "message"),
    [
        (with_parameters(fade={"shape": "hann", "duration_seconds": "0.02"}), "hann"),
        (with_parameters(fade=None), "no fade"),
        (with_parameters(frequency_hz=None), "no frequency_hz"),
        (with_parameters(level_db_spl=None), "no level_db_spl"),
        (with_parameters(frequency_hz="24000.0"), "half the sample rate"),
        (with_parameters(level_db_spl="100.0"), "clip"),
        (with_parameters(frequency_hz="1_000.0"), "not a decimal"),
        (with_parameters(frequency_hz="01000.0"), "not a decimal"),
        (with_parameters(level_db_spl=60.0), "has to be a string"),
        (
            with_parameters(fade={"shape": "linear", "duration_seconds": "0.6"}),
            "do not fit",
        ),
        (
            with_parameters(fade={"shape": "none", "duration_seconds": "0.02"}),
            "no shape has no duration",
        ),
        (
            with_parameters(fade={"shape": "linear", "duration_seconds": "0"}),
            "which shapes nothing",
        ),
        (described(kind="noise"), "renders 'sinusoid'"),
        (described(sample_rate=0), "sample_rate is 0"),
        (described(channels=0), "channels is 0"),
        (described(duration_seconds="0.0"), "duration_seconds is 0"),
        (described(bit_depth=8), "bit_depth 8"),
    ],
)
def test_a_description_the_generator_cannot_render_is_refused(
    description: Mapping[str, Any], message: str
) -> None:
    """Each refusal names the field, so a fixture author knows what to fix."""
    with pytest.raises(DescriptionError, match=message):
        parse_sinusoid(description)


def test_a_signal_shorter_than_one_sample_is_refused() -> None:
    """A duration that rounds to no samples has nothing to measure."""
    description = with_parameters(fade={"shape": "none", "duration_seconds": "0"})
    description["sample_rate"] = 8000
    description["duration_seconds"] = "0.00001"

    with pytest.raises(DescriptionError, match="less than one sample"):
        parse_sinusoid(description)


def test_encoding_at_a_depth_the_generator_does_not_write_is_refused() -> None:
    """The encoder refuses the same set the parser does, from its own side."""
    with pytest.raises(DescriptionError, match="bit_depth 12"):
        encode_pcm([0.0], 12)


def test_a_full_scale_peak_does_not_overflow_the_depth() -> None:
    """Scaling by 32767 rather than 32768 keeps a positive peak inside range.

    docs/calibration.md gives the reason: the negative end of a two's
    complement range reaches one step further than the positive end.
    """
    frames = encode_pcm([1.0, -1.0], 16)
    values = [
        int.from_bytes(frames[index : index + 2], "little", signed=True)
        for index in (0, 2)
    ]

    assert values == [32767, -32767]


def test_the_encoder_clamps_a_sample_outside_the_range() -> None:
    """A caller handing the encoder more than full scale gets full scale.

    `parse_sinusoid` refuses a description whose peak would clip, so nothing
    this module renders reaches this. The encoder takes samples rather than a
    description, and the modulated generator in issue #23 produces an envelope
    that can exceed the carrier's peak, so the clamp is the difference between
    a saturated sample and an integer that wraps to the opposite sign.
    """
    frames = encode_pcm([1.4, -1.4], 16)
    values = [
        int.from_bytes(frames[index : index + 2], "little", signed=True)
        for index in (0, 2)
    ]

    assert values == [32767, -32768]


def test_the_dataclass_is_frozen() -> None:
    """A parsed description is not edited after it has been checked."""
    signal = parse_sinusoid(BASE)

    with pytest.raises(AttributeError):
        signal.frequency_hz = 2000.0  # type: ignore[misc]

    assert isinstance(signal, Sinusoid)
