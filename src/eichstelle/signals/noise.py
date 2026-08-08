"""The noise generators, and the random stream they are reproducible through.

A tone is reproducible because its description determines it. A noise is not:
the samples come from a pseudo-random sequence, and that sequence depends on an
algorithm, a seed and the version of whatever produced it. None of the three is
visible in the output. Two runs of one fixture on two machines can produce two
different noises, both looking exactly like noise, and the metric difference
that follows is indistinguishable from an implementation disagreeing.

So the sequence is not borrowed. This module implements the bit generator, and
the description names it and its seed. `random.random` and a numeric library's
default generator are both refused here for the same reason: their streams are
their maintainers' to change, a change moves every noise fixture at once, and
nothing in a fixture would record that it had happened. `docs/fixtures.md` says
this in the place a fixture author will read it.

Nothing here reaches for NumPy, which is the choice `generator.py` already made
for the sinusoid and is a stronger choice here. The filter and the bit generator
are the parts of a noise fixture that have to be bit-exact, and taking either
from a library makes this project's stimulus depend on that library's release
notes.

## The three things a noise description has to say

The stream, meaning the algorithm and the seed. Without both the samples are
not reproducible at all.

The spectral shape, for broadband noise. `white` and `pink` are different
stimuli and a metric answers differently for each.

The filter, for band-limited noise, and this is the one that gets left out. A
one-bark-wide band made with a brick wall and one made with a realisable filter
of stated order are different signals with different metric values. The edges
alone do not describe the stimulus, so the type and the order are required
beside them.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from eichstelle.signals.generator import (
    DescriptionError,
    Fade,
    _decimal,
    _fade,
    _gain,
    _integer,
)

# The kinds this module renders.
NOISE: Final = "noise"
BAND_LIMITED_NOISE: Final = "band_limited_noise"

# The bit generators this module implements, by the name a description uses.
# One entry today. A second one is added by implementing it here, never by
# reaching for a library default: the point of the field is that the name
# identifies a sequence this repository can reproduce forever.
RANDOM_ALGORITHMS: Final = ("xoshiro256plusplus",)

# The broadband shapes. `white` is the raw stream. `pink` is the ladder below,
# whose deviation from an exact minus three decibels per octave is measured by
# the suite rather than claimed here.
SPECTRAL_SHAPES: Final = ("white", "pink")

# The band-pass families. `butterworth` is maximally flat in the pass band,
# which is what a fixture wants when the band edges are the statement being
# made. A brick wall is a different stimulus and would be a second entry.
FILTER_TYPES: Final = ("butterworth",)

# The prototype orders this module designs. The realised band-pass carries twice
# as many poles as the prototype, for the reason `_butterworth_bandpass` gives,
# and the skirts fall at six decibels per octave per prototype order. Eight is
# the ceiling because a cascade of eight biquads at a narrow band is where
# double precision starts to matter and nothing has asked for more.
FILTER_ORDERS: Final = (1, 2, 3, 4, 5, 6, 7, 8)

_MASK64: Final = (1 << 64) - 1

# The pink ladder's span and density. Poles are spaced logarithmically from
# `_PINK_LOWEST_HZ` to a fraction of the sample rate, `_PINK_POLES_PER_DECADE`
# of them per decade, with each zero placed at the geometric mean of its pole
# and the next. Between a pole and its zero the response falls at six decibels
# per octave and between a zero and the next pole it is flat, so the average is
# three, and the ripple around it is what the density buys.
_PINK_LOWEST_HZ: Final = 1.0
_PINK_POLES_PER_DECADE: Final = 3.0
_PINK_HIGHEST_FRACTION: Final = 0.45


def _rotl(value: int, count: int) -> int:
    """Rotate a 64-bit word left, which is what the generator is written in."""
    return ((value << count) | (value >> (64 - count))) & _MASK64


def _splitmix64(state: int) -> tuple[int, int]:
    """One step of SplitMix64, used only to fill the state from one seed.

    A seed is one number and the generator holds four words. Expanding it with
    the same generator would correlate the first outputs with the seed, which is
    the documented reason SplitMix64 exists beside xoshiro at all.
    """
    state = (state + 0x9E3779B97F4A7C15) & _MASK64
    mixed = state
    mixed = ((mixed ^ (mixed >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    mixed = ((mixed ^ (mixed >> 27)) * 0x94D049BB133111EB) & _MASK64
    return (mixed ^ (mixed >> 31)) & _MASK64, state


def words(seed: int) -> Iterator[int]:
    """The raw 64-bit stream for a seed, forever.

    xoshiro256++. The state is filled from the seed with SplitMix64 and the
    step is the published one. Written out here rather than imported so that
    the sequence a fixture names is defined by a file in this repository, which
    is the whole point of naming an algorithm in a description.
    """
    state = seed & _MASK64
    words_out: list[int] = []
    for _ in range(4):
        value, state = _splitmix64(state)
        words_out.append(value)
    s0, s1, s2, s3 = words_out

    while True:
        yield (_rotl((s0 + s3) & _MASK64, 23) + s0) & _MASK64
        shifted = (s1 << 17) & _MASK64
        s2 ^= s0
        s3 ^= s1
        s1 ^= s2
        s0 ^= s3
        s2 ^= shifted
        s3 = _rotl(s3, 45)


def _uniforms(seed: int) -> Iterator[float]:
    """Doubles in the half-open unit interval, from the top 53 bits of each word.

    The top bits rather than the bottom, and 53 of them rather than 64, because
    a double holds 53 bits of mantissa and taking more would round.
    """
    for word in words(seed):
        yield (word >> 11) * (2.0**-53)


def gaussians(seed: int) -> Iterator[float]:
    """Standard normal samples, by the Box-Muller transform.

    Two uniforms in and two samples out, every time, so the number of draws per
    sample is fixed. A rejection method would consume a variable number of
    words, which is still deterministic and much harder to reason about when
    somebody asks why two streams diverged.

    A uniform of exactly zero would put a logarithm at negative infinity, and
    the stream produces one roughly once in nine million million draws. It is
    handled rather than assumed away: the pair is redrawn.
    """
    stream = _uniforms(seed)
    while True:
        first = next(stream)
        second = next(stream)
        if first <= 0.0:
            continue
        radius = math.sqrt(-2.0 * math.log(first))
        angle = 2.0 * math.pi * second
        yield radius * math.cos(angle)
        yield radius * math.sin(angle)


@dataclass(frozen=True)
class Biquad:
    """One second-order section, as the coefficients a cascade applies."""

    b0: float
    b1: float
    b2: float
    a1: float
    a2: float


@dataclass(frozen=True)
class Band:
    """The band-pass a band-limited description declares."""

    low_edge_hz: float
    high_edge_hz: float
    filter_type: str
    filter_order: int


@dataclass(frozen=True)
class Noise:
    """A noise description that has been checked and converted.

    One class for both kinds. `band` is set on the band-limited kind and None on
    the broadband one, and `spectral_shape` is the other way round, which is
    what `parse_noise` guarantees.
    """

    kind: str
    random_algorithm: str
    random_seed: int
    spectral_shape: str | None
    band: Band | None
    level_db_spl: float
    calibration_reference_db_spl: float
    sample_rate: int
    channels: int
    duration_seconds: float
    bit_depth: int | None
    fade: Fade

    @property
    def frame_count(self) -> int:
        """How many samples per channel the signal holds."""
        return round(self.duration_seconds * self.sample_rate)

    @property
    def fade_frames(self) -> int:
        """How many samples each of the two fades covers."""
        if self.fade.shape == "none":
            return 0
        return round(self.fade.duration_seconds * self.sample_rate)

    @property
    def target_rms(self) -> float:
        """The root mean square the sustain is scaled to.

        `docs/calibration.md` fixes the reference as the level of a sinusoid
        whose PEAK sample is one, and the level names a root mean square. So a
        signal at the reference level has a root mean square of one over the
        square root of two, and every other level is that scaled by the decibel
        difference. Reading the reference as a root mean square instead would
        put every noise fixture 3.01 dB out, in the same direction, against
        every tone fixture in the same set.
        """
        full = 10 ** ((self.level_db_spl - self.calibration_reference_db_spl) / 20)
        return full / math.sqrt(2.0)


def _bounded_integer(source: Mapping[str, object], field: str, where: str) -> int:
    """Read an integer field that has to be present, saying which one is missing."""
    if field not in source:
        raise DescriptionError(f"{where}: no {field}")
    return _integer(source, field, where)


def _parse_band(source: Mapping[str, object], where: str, sample_rate: int) -> Band:
    """Check the four fields that make a band-limited stimulus a stimulus."""
    filter_type = source.get("filter_type")
    if filter_type not in FILTER_TYPES:
        implemented = ", ".join(FILTER_TYPES)
        raise DescriptionError(
            f"{where}: filter_type is {filter_type!r} and this generator builds "
            f"{implemented}. The filter is part of the stimulus rather than a "
            f"detail of how the band was made"
        )

    order = _bounded_integer(source, "filter_order", where)
    if order not in FILTER_ORDERS:
        implemented = ", ".join(str(value) for value in FILTER_ORDERS)
        raise DescriptionError(
            f"{where}: filter_order is {order} and this generator designs {implemented}"
        )

    low = _decimal(source, "low_edge_hz", where)
    high = _decimal(source, "high_edge_hz", where)
    if low <= 0:
        raise DescriptionError(f"{where}: low_edge_hz is {low}")
    if high <= low:
        raise DescriptionError(
            f"{where}: high_edge_hz is {high} and low_edge_hz is {low}, so the "
            f"band is empty or inverted"
        )
    nyquist = sample_rate / 2.0
    if high >= nyquist:
        raise DescriptionError(
            f"{where}: high_edge_hz is {high} and the Nyquist frequency at "
            f"{sample_rate} Hz is {nyquist}. A band reaching it cannot be "
            f"represented, and a filter designed for one is not the filter the "
            f"description asked for"
        )
    return Band(
        low_edge_hz=low,
        high_edge_hz=high,
        filter_type=filter_type,
        filter_order=order,
    )


def parse_noise(description: Mapping[str, object]) -> Noise:
    """Check a `signal` object of a noise kind and convert its fields.

    Every refusal here is a way a noise fixture stops being reproducible while
    still looking like a fixture. The one the issue that built this names first
    is the missing seed, and it is refused rather than defaulted: a default seed
    inside a generator is a stimulus nobody wrote down.
    """
    where = "signal"
    kind = description.get("kind")
    if kind not in (NOISE, BAND_LIMITED_NOISE):
        raise DescriptionError(
            f"{where}: kind is {kind!r} and this generator renders "
            f"{NOISE!r} and {BAND_LIMITED_NOISE!r}"
        )

    sample_rate = _integer(description, "sample_rate", where)
    if sample_rate < 1:
        raise DescriptionError(f"{where}: sample_rate is {sample_rate}")
    channels = _integer(description, "channels", where)
    if channels < 1:
        raise DescriptionError(f"{where}: channels is {channels}")
    duration = _decimal(description, "duration_seconds", where)
    if duration <= 0:
        raise DescriptionError(f"{where}: duration_seconds is {duration}")

    bit_depth: int | None = None
    if "bit_depth" in description:
        bit_depth = _integer(description, "bit_depth", where)

    parameters = description.get("parameters")
    if not isinstance(parameters, Mapping):
        raise DescriptionError(f"{where}: no parameters object")
    inner = f"{where}.parameters"

    algorithm = parameters.get("random_algorithm")
    if algorithm not in RANDOM_ALGORITHMS:
        implemented = ", ".join(RANDOM_ALGORITHMS)
        raise DescriptionError(
            f"{inner}: random_algorithm is {algorithm!r} and this generator "
            f"implements {implemented}. The seed alone does not identify a "
            f"sequence"
        )

    if "random_seed" not in parameters:
        raise DescriptionError(
            f"{inner}: no random_seed. A noise with no seed is a different "
            f"stimulus on every run and nothing in the fixture would say so"
        )
    seed = _integer(parameters, "random_seed", inner)
    if seed < 0:
        raise DescriptionError(f"{inner}: random_seed is {seed}")

    shape: str | None = None
    band: Band | None = None
    if kind == NOISE:
        shape = parameters.get("spectral_shape")
        if shape not in SPECTRAL_SHAPES:
            implemented = ", ".join(SPECTRAL_SHAPES)
            raise DescriptionError(
                f"{inner}: spectral_shape is {shape!r} and this generator "
                f"produces {implemented}"
            )
    else:
        band = _parse_band(parameters, inner, sample_rate)

    level = _decimal(parameters, "level_db_spl", inner)
    reference = _decimal(parameters, "calibration_reference_db_spl", inner)
    fade = _fade(parameters, inner)

    return Noise(
        kind=kind,
        random_algorithm=algorithm,
        random_seed=seed,
        spectral_shape=shape,
        band=band,
        level_db_spl=level,
        calibration_reference_db_spl=reference,
        sample_rate=sample_rate,
        channels=channels,
        duration_seconds=duration,
        bit_depth=bit_depth,
        fade=fade,
    )


def _pink_ladder(sample_rate: int) -> list[tuple[float, float, float]]:
    """First-order sections approximating minus three decibels per octave.

    A cascade of pole-zero pairs, logarithmically spaced. Each section falls at
    six decibels per octave between its pole and its zero and is flat above it,
    so an interleaved ladder averages three, and how closely it does that is the
    spacing. The alternative, a set of coefficients published for one sample
    rate, would be wrong at every other sample rate a fixture may declare, and a
    fixture states its sample rate.

    Returned as `(gain, pole_coefficient, zero_coefficient)` triples for the
    one-pole one-zero difference equation the renderer runs.
    """
    highest = _PINK_HIGHEST_FRACTION * sample_rate
    if highest <= _PINK_LOWEST_HZ:
        raise DescriptionError(
            f"signal: a sample rate of {sample_rate} Hz leaves no room for the "
            f"pink shaping ladder, which spans from {_PINK_LOWEST_HZ} Hz"
        )
    decades = math.log10(highest / _PINK_LOWEST_HZ)
    count = max(1, round(decades * _PINK_POLES_PER_DECADE))
    step = decades / count

    sections: list[tuple[float, float, float]] = []
    for index in range(count):
        pole_hz = _PINK_LOWEST_HZ * 10 ** (index * step)
        zero_hz = pole_hz * 10 ** (step / 2.0)
        pole = math.exp(-2.0 * math.pi * pole_hz / sample_rate)
        zero = math.exp(-2.0 * math.pi * zero_hz / sample_rate)
        # Unit gain at high frequency, where both the pole and the zero are
        # already behind. Overall level is set by the measured scaling later, so
        # only the shape of the cascade matters here.
        sections.append((1.0, pole, zero))
    return sections


def _apply_pink(samples: list[float], sample_rate: int) -> list[float]:
    """Run the ladder over the samples, in place of a library's pink noise."""
    out = list(samples)
    for gain, pole, zero in _pink_ladder(sample_rate):
        previous_in = 0.0
        previous_out = 0.0
        for index, value in enumerate(out):
            filtered = gain * (value - zero * previous_in) + pole * previous_out
            previous_in = value
            previous_out = filtered
            out[index] = filtered
    return out


def _butterworth_bandpass(
    low_edge_hz: float, high_edge_hz: float, order: int, sample_rate: int
) -> tuple[list[Biquad], float]:
    """Design the band-pass, as biquads and a gain.

    The prototype is a Butterworth low-pass of `order` poles. The low-pass to
    band-pass substitution maps each of them to two, so the realised filter
    carries twice as many poles as the order names and its skirts fall at six
    decibels per octave per prototype order. That factor of two is stated in
    `docs/fixtures.md` as well, because a fixture author writing `4` and
    expecting a fourth-order response would be describing a different stimulus
    from the one produced.

    The bilinear transform warps frequency, so the edges are pre-warped before
    the design and land where the description asked for them rather than near
    it. The gain normalises the response to one at the geometric centre.
    """
    rate = float(sample_rate)
    warped_low = 2.0 * rate * math.tan(math.pi * low_edge_hz / rate)
    warped_high = 2.0 * rate * math.tan(math.pi * high_edge_hz / rate)
    width = warped_high - warped_low
    centre_squared = warped_low * warped_high

    poles: list[complex] = []
    for index in range(order):
        angle = math.pi * (2 * index + order + 1) / (2 * order)
        prototype = complex(math.cos(angle), math.sin(angle))
        if prototype.imag < -1e-12:
            # Its conjugate is already in the list, and taking both would build
            # the same section twice.
            continue
        half = width * prototype / 2.0
        offset = _complex_sqrt(half * half - centre_squared)
        first = half + offset
        second = half - offset
        if abs(prototype.imag) <= 1e-12:
            # A real prototype pole, which happens at odd orders. Its two images
            # are each other's conjugate, so they are one section rather than
            # two.
            poles.append(first)
        else:
            poles.append(first)
            poles.append(second)

    sections: list[Biquad] = []
    for pole in poles:
        digital = (2.0 * rate + pole) / (2.0 * rate - pole)
        sections.append(
            Biquad(
                b0=1.0,
                b1=0.0,
                b2=-1.0,
                a1=-2.0 * digital.real,
                a2=abs(digital) ** 2,
            )
        )

    centre_hz = rate / math.pi * math.atan(math.sqrt(centre_squared) / (2.0 * rate))
    magnitude = _cascade_magnitude(sections, 1.0, centre_hz, sample_rate)
    if magnitude == 0.0:  # pragma: no cover - a degenerate design, not reachable
        raise DescriptionError("signal: the band-pass design has no pass band")
    return sections, 1.0 / magnitude


def _complex_sqrt(value: complex) -> complex:
    """A square root that stays on one branch, so a design is deterministic."""
    return complex(value) ** 0.5


def _cascade_magnitude(
    sections: Sequence[Biquad], gain: float, frequency_hz: float, sample_rate: int
) -> float:
    """The magnitude response of the cascade at one frequency.

    Used by the design to normalise itself, and by the suite to compare the
    cascade against the Butterworth formula it is supposed to realise.
    """
    unit = complex(
        math.cos(-2.0 * math.pi * frequency_hz / sample_rate),
        math.sin(-2.0 * math.pi * frequency_hz / sample_rate),
    )
    response = complex(gain, 0.0)
    for section in sections:
        numerator = section.b0 + section.b1 * unit + section.b2 * unit * unit
        denominator = 1.0 + section.a1 * unit + section.a2 * unit * unit
        response *= numerator / denominator
    return abs(response)


def _apply_sections(
    samples: list[float], sections: Sequence[Biquad], gain: float
) -> list[float]:
    """Run a biquad cascade over the samples, transposed direct form two."""
    out = [value * gain for value in samples]
    for section in sections:
        first = 0.0
        second = 0.0
        for index, value in enumerate(out):
            filtered = section.b0 * value + first
            first = section.b1 * value - section.a1 * filtered + second
            second = section.b2 * value - section.a2 * filtered
            out[index] = filtered
    return out


def render_noise(signal: Noise) -> list[float]:
    """The samples, interleaved by channel, in a range of minus one to plus one.

    The order of operations is the part worth reading. The stream is drawn, then
    shaped or filtered, then MEASURED, then scaled, and only then faded. The
    measurement is what makes the fixture's stated level true: a filter has pass
    band ripple and a shaping ladder has its own, so a level computed from theory
    and a level measured from the samples differ, and the fixture's number has to
    be the one a meter would read.

    Scaling before the fade is the same convention the sinusoid generator
    carries, and `docs/calibration.md` states it: the level names the tone rather
    than the produced file, so the root mean square over the SUSTAIN is the
    requested level and the root mean square over the whole signal is lower by an
    amount the fade decides.

    Every channel carries the same samples. Two independent noises in two
    channels would be a different stimulus and the description has no field
    saying which was meant.
    """
    frames = signal.frame_count
    stream = gaussians(signal.random_seed)
    samples = [next(stream) for _ in range(frames)]

    if signal.band is not None:
        sections, gain = _butterworth_bandpass(
            signal.band.low_edge_hz,
            signal.band.high_edge_hz,
            signal.band.filter_order,
            signal.sample_rate,
        )
        samples = _apply_sections(samples, sections, gain)
    elif signal.spectral_shape == "pink":
        samples = _apply_pink(samples, signal.sample_rate)

    fade_frames = signal.fade_frames
    sustain = samples[fade_frames : frames - fade_frames] if fade_frames else samples
    if not sustain:
        raise DescriptionError(
            "signal: the two fades cover the whole signal, so there is no "
            "sustain to measure a level over"
        )
    measured = math.sqrt(sum(value * value for value in sustain) / len(sustain))
    if measured == 0.0:  # pragma: no cover - a silent stream, not reachable
        raise DescriptionError("signal: the filtered stream is silent")

    scale = signal.target_rms / measured
    scaled = [value * scale for value in samples]

    peak = max(abs(value) for value in scaled)
    if peak > 1.0:
        raise DescriptionError(
            f"signal: at {signal.level_db_spl} dB against a reference of "
            f"{signal.calibration_reference_db_spl} dB the samples reach "
            f"{peak:.4f}, which is outside the range a sample holds. A noise "
            f"has peaks well above its root mean square, so a level a tone "
            f"carries may still clip here"
        )

    out: list[float] = []
    for index, value in enumerate(scaled):
        shaped = value * _gain(index, frames, fade_frames, signal.fade.shape)
        out.extend([shaped] * signal.channels)
    return out
