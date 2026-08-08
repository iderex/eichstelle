"""The sinusoid generator, and every description it refuses.

What it produces is decided by ``docs/calibration.md`` and by the ``sinusoid``
entry in ``schema/fixture-1.schema.json``. This module adds no convention of its
own except the two the document defers to the generator: the permitted fade
shapes, and what the fade does to the level.

The level names the tone. A fade shapes the ends of the signal and does not
change what the tone was asked to be, so the root mean square measured over the
whole signal is lower than the requested level by an amount that depends on the
fade, and the root mean square measured over the sustain is the requested level.
The alternative reading, where the level names the produced signal including its
fades, would make the amplitude depend on the fade duration and would put a
different tone in front of an implementation every time a fade was adjusted.

Nothing here reaches for NumPy. A sinusoid, a fade and an integer encoding need
the standard library, decision record 0002 permits the dependency without
requiring it, and taking it here would take it for the whole package on the
strength of the easiest case rather than the hardest.
"""

from __future__ import annotations

import math
import re
import wave
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

# The kinds this module renders. A second kind arrives with the generator that
# produces it, which for the modulated signals is issue #23.
SINUSOID: Final = "sinusoid"

# The permitted fade shapes. `docs/calibration.md` said the set belongs here,
# and the schema deliberately does not enumerate it, so an unknown shape is
# refused by this module rather than by a JSON keyword.
#
# `linear` is a straight ramp in amplitude. `raised_cosine` is a half Hann
# window, which is continuous in its first derivative at both ends of the ramp
# and therefore spreads less energy away from the tone than a linear ramp with
# the same duration. `none` applies no shaping at all and is the one that can
# produce a click: unless the duration holds a whole number of periods, the
# signal stops at a non-zero sample, which is broadband energy the metric will
# see. It is here because some stationary cases want the unshaped tone, and it
# is named `none` rather than reached by writing a zero duration so that a
# fixture asking for it has said so.
FADE_SHAPES: Final = ("none", "linear", "raised_cosine")

# The integer depths this module encodes. The schema admits any depth from eight
# up; these three are what is implemented, and eight is refused rather than
# guessed at because eight-bit WAVE is unsigned offset binary rather than the
# signed mapping `docs/calibration.md` works through, and no fixture has asked
# for it. Adding it is a change to this table and to that document together.
INTEGER_DEPTHS: Final = (16, 24, 32)

# A decimal as the schema writes one. Every physical quantity in a fixture is a
# string, because a JSON number is an IEEE 754 double in every parser this
# project will meet. The conversion happens here, once, and deliberately.
DECIMAL: Final = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?$")


class DescriptionError(ValueError):
    """The description cannot be rendered, and the message says which field."""


@dataclass(frozen=True)
class Fade:
    """The onset and offset shaping, as the description states it."""

    shape: str
    duration_seconds: float


@dataclass(frozen=True)
class Sinusoid:
    """A sinusoid description that has been checked and converted.

    Every field here came from the description. Nothing is defaulted, because
    the point of the refusals below is that a missing field is visible.
    """

    frequency_hz: float
    level_db_spl: float
    calibration_reference_db_spl: float
    sample_rate: int
    channels: int
    duration_seconds: float
    bit_depth: int | None
    fade: Fade

    @property
    def frame_count(self) -> int:
        """How many samples per channel the signal holds.

        Rounded rather than truncated, so a duration that lands a hair under a
        whole number of samples in binary floating point produces the count a
        reader counted rather than one fewer.
        """
        return round(self.duration_seconds * self.sample_rate)

    @property
    def peak_amplitude(self) -> float:
        """The peak sample of the tone, in a range of minus one to plus one.

        `docs/calibration.md` derives this. A full-scale sine wave is one whose
        peak sample is one, not one whose root mean square is one, and the
        difference between those readings is 3.01 dB on every fixture at once.
        """
        return 10 ** ((self.level_db_spl - self.calibration_reference_db_spl) / 20)

    @property
    def fade_frames(self) -> int:
        """How many samples each of the two fades covers."""
        if self.fade.shape == "none":
            return 0
        return round(self.fade.duration_seconds * self.sample_rate)


def _decimal(source: Mapping[str, object], field: str, where: str) -> float:
    """Read one decimal-string field, or say exactly what is wrong with it."""
    if field not in source:
        raise DescriptionError(f"{where}: no {field}")
    value = source[field]
    if not isinstance(value, str):
        raise DescriptionError(
            f"{where}: {field} is {type(value).__name__} and has to be a string. "
            "Every physical quantity in a fixture is written as text so that it "
            "survives a parser unchanged"
        )
    if not DECIMAL.match(value):
        raise DescriptionError(f"{where}: {field} is not a decimal: {value!r}")
    try:
        return float(Decimal(value))
    except InvalidOperation as exc:  # pragma: no cover - the pattern precedes it
        raise DescriptionError(f"{where}: {field} is not a decimal: {value!r}") from exc


def _integer(source: Mapping[str, object], field: str, where: str) -> int:
    """Read one count field. A count stays a JSON number and is exact."""
    if field not in source:
        raise DescriptionError(f"{where}: no {field}")
    value = source[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise DescriptionError(
            f"{where}: {field} is {type(value).__name__} and has to be an integer"
        )
    return value


def _fade(source: Mapping[str, object], where: str) -> Fade:
    """Read the fade object, refusing a shape this module does not implement."""
    if "fade" not in source:
        raise DescriptionError(f"{where}: no fade")
    raw = source["fade"]
    if not isinstance(raw, Mapping):
        raise DescriptionError(f"{where}: fade is not an object")
    if "shape" not in raw:
        raise DescriptionError(f"{where}.fade: no shape")
    shape = raw["shape"]
    if not isinstance(shape, str) or shape not in FADE_SHAPES:
        permitted = ", ".join(FADE_SHAPES)
        raise DescriptionError(
            f"{where}.fade: shape {shape!r} is not one this generator produces. "
            f"Permitted: {permitted}"
        )
    duration = _decimal(raw, "duration_seconds", f"{where}.fade")
    if duration < 0:
        raise DescriptionError(f"{where}.fade: duration_seconds is negative")
    if shape == "none" and duration != 0:
        raise DescriptionError(
            f"{where}.fade: shape none carries duration_seconds {duration}, and a "
            "fade of no shape has no duration. Name a shape or write 0"
        )
    if shape != "none" and duration == 0:
        raise DescriptionError(
            f"{where}.fade: shape {shape} carries duration_seconds 0, which shapes "
            "nothing. Write shape none if that is what is wanted"
        )
    return Fade(shape=shape, duration_seconds=duration)


def parse_sinusoid(description: Mapping[str, object]) -> Sinusoid:
    """Check a `signal` object of kind `sinusoid` and convert its fields.

    This is where a description is refused. It does not assume the schema has
    run: a caller holding a description from somewhere else gets the same
    refusals, and the two overlap on purpose rather than by accident.
    """
    where = "signal"
    kind = description.get("kind")
    if kind != SINUSOID:
        raise DescriptionError(
            f"{where}: kind is {kind!r} and this generator renders {SINUSOID!r}"
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
        if bit_depth not in INTEGER_DEPTHS:
            implemented = ", ".join(str(depth) for depth in INTEGER_DEPTHS)
            raise DescriptionError(
                f"{where}: bit_depth {bit_depth} is not one this generator writes. "
                f"Implemented: {implemented}. Eight-bit WAVE is unsigned offset "
                "binary rather than the signed mapping docs/calibration.md works "
                "through, so it is refused rather than guessed at"
            )

    parameters = description.get("parameters")
    if not isinstance(parameters, Mapping):
        raise DescriptionError(f"{where}: no parameters object")
    inside = f"{where}.parameters"

    frequency = _decimal(parameters, "frequency_hz", inside)
    if frequency <= 0:
        raise DescriptionError(f"{inside}: frequency_hz is {frequency}")
    if frequency * 2 >= sample_rate:
        raise DescriptionError(
            f"{inside}: frequency_hz {frequency} is at or above half the sample "
            f"rate {sample_rate}, so what would be generated is an alias of a "
            "different tone rather than this one"
        )
    level = _decimal(parameters, "level_db_spl", inside)

    # The refusal this issue names first. A generator that supplied a reference
    # would put a convention nobody wrote down behind every fixture that forgot
    # to state one, and the error would be a constant offset on all of them.
    if "calibration_reference_db_spl" not in parameters:
        raise DescriptionError(
            f"{inside}: no calibration_reference_db_spl. The level of a full-scale "
            "sine wave is what makes a level in decibels mean a pressure, and this "
            "generator has no default for it. docs/calibration.md says what the "
            "field means"
        )
    reference = _decimal(parameters, "calibration_reference_db_spl", inside)

    signal = Sinusoid(
        frequency_hz=frequency,
        level_db_spl=level,
        calibration_reference_db_spl=reference,
        sample_rate=sample_rate,
        channels=channels,
        duration_seconds=duration,
        bit_depth=bit_depth,
        fade=_fade(parameters, inside),
    )

    if signal.frame_count < 1:
        raise DescriptionError(
            f"{where}: duration_seconds {duration} at sample_rate {sample_rate} "
            "is less than one sample"
        )
    if 2 * signal.fade_frames > signal.frame_count:
        raise DescriptionError(
            f"{inside}.fade: two fades of {signal.fade_frames} samples do not fit "
            f"in {signal.frame_count} samples. A signal that is all fade has no "
            "tone in it to measure"
        )
    if signal.peak_amplitude > 1:
        raise DescriptionError(
            f"{inside}: level_db_spl {level} is above the calibration reference "
            f"{reference}, so the peak sample would be {signal.peak_amplitude:.6f} "
            "and clip. Raise the reference or lower the level"
        )
    return signal


def _gain(index: int, frames: int, fade_frames: int, shape: str) -> float:
    """The fade gain at one sample.

    Zero at the first and the last sample, one across the sustain. The ramp is
    written as a position from zero to one and shaped once, so the two shapes
    differ in one expression rather than in two branches that can drift.
    """
    if fade_frames == 0:
        return 1.0
    if index < fade_frames:
        position = index / fade_frames
    elif index >= frames - fade_frames:
        position = (frames - 1 - index) / fade_frames
    else:
        return 1.0
    if shape == "linear":
        return position
    return 0.5 * (1.0 - math.cos(math.pi * position))


def render(signal: Sinusoid) -> list[float]:
    """The samples, interleaved by channel, in a range of minus one to plus one.

    Every channel carries the same tone. A sinusoid starts at phase zero, which
    is why its first sample is zero before any fade is applied; the schema
    carries no phase field for this kind and this module supplies none.
    """
    frames = signal.frame_count
    fade_frames = signal.fade_frames
    amplitude = signal.peak_amplitude
    step = 2.0 * math.pi * signal.frequency_hz / signal.sample_rate
    samples: list[float] = []
    for index in range(frames):
        value = amplitude * math.sin(step * index)
        value *= _gain(index, frames, fade_frames, signal.fade.shape)
        samples.extend([value] * signal.channels)
    return samples


def encode_pcm(samples: list[float], bit_depth: int) -> bytes:
    """The samples as little-endian signed integer frames.

    The scale is the largest positive value the depth holds, which for sixteen
    bits is 32767 and not 32768, for the reason `docs/calibration.md` gives: the
    negative end of a two's complement range reaches one step further than the
    positive end, and scaling by the larger number puts a full-scale positive
    peak one step outside what can be stored.

    Rounding is half away from zero rather than Python's half to even, because
    the mapping in that document is what a reader checks a sample against by
    hand and 654 is what they will have computed.
    """
    if bit_depth not in INTEGER_DEPTHS:
        implemented = ", ".join(str(depth) for depth in INTEGER_DEPTHS)
        raise DescriptionError(
            f"bit_depth {bit_depth} is not one this generator writes. "
            f"Implemented: {implemented}"
        )
    full = 2 ** (bit_depth - 1) - 1
    floor = -(2 ** (bit_depth - 1))
    width = bit_depth // 8
    out = bytearray()
    for value in samples:
        scaled = value * full
        integer = math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)
        integer = max(floor, min(full, integer))
        out.extend(integer.to_bytes(width, "little", signed=True))
    return bytes(out)


def write_wave(path: Path, signal: Sinusoid) -> Path:
    """Render the description and write it as a WAVE file at `path`.

    Integer depths only. A float WAVE is format 3 rather than format 1 and the
    standard library's writer does not produce one, so a description with no
    `bit_depth` is refused here rather than written out at a depth nobody chose.

    The container is not what a fixture's claim is about. Issue #25 hashes the
    samples and the format parameters and no container bytes at all, so two
    files differing only in chunk layout are the same stimulus.
    """
    if signal.bit_depth is None:
        raise DescriptionError(
            "signal: no bit_depth, and a WAVE file has to be written at one. "
            "Render the samples instead, or state a bit_depth"
        )
    frames = encode_pcm(render(signal), signal.bit_depth)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(signal.channels)
        handle.setsampwidth(signal.bit_depth // 8)
        handle.setframerate(signal.sample_rate)
        handle.writeframes(frames)
    return path
