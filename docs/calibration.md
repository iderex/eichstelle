# What a level in a signal description means

A sample in a WAVE file is a dimensionless number. A loudness in sone is a
physical quantity. Something has to say what digital full scale corresponds to
in pascals, and something has to say what "sixty decibels" means once a carrier
has been modulated. Both answers are conventions, both have a competing
convention in circulation, and picking the wrong one moves every result by a
fixed amount for a reason that has nothing to do with the psychoacoustic model
under test.

That is the failure this file exists to prevent. A constant offset on every
fixture is a real finding worth reporting, and it is worthless if the suite
cannot tell it apart from a model disagreement.

This file fixes both conventions and works each one through with numbers. It
does not describe a generator: nothing here generates a signal yet. Issue #21
builds the sinusoid generator and issue #23 the modulated one, and both of them
are held to what is written here.

## The calibration reference

Every signal description states the sound pressure level, in decibels relative
to twenty micropascals, that a full-scale sine wave corresponds to. It is never
a default inside a generator, and an implementation that cannot be told its
calibration is a limitation the adapter declares rather than something the
harness guesses around.

A full-scale sine wave here means a sinusoid whose peak sample is one, in a
representation whose range is minus one to plus one. Not a signal whose root
mean square is one. The difference between those two readings is 3.01 dB and it
would apply to every fixture at once.

So, writing the reference as `Lfs` and the wanted level as `L`, both in decibels
SPL:

    peak amplitude = 10 ** ((L - Lfs) / 20)

and the root mean square of that sinusoid is the peak divided by the square root
of two. The sound pressure the level names is the root mean square pressure,
which is the usual reading of a level and is stated here because the alternative
reading exists.

### Worked example

A reference of 94.0 dB SPL and a tone at 60.0 dB SPL:

    $ python -c "print(10 ** ((60.0 - 94.0) / 20))"
    0.0199526231496888

    $ python - <<'EOF'
    import math
    Lfs, L = 94.0, 60.0
    peak = 10 ** ((L - Lfs) / 20)
    rows = [
        ("peak amplitude", f"{peak:.12f}"),
        ("root mean square", f"{peak / math.sqrt(2):.12f}"),
        ("pressure at 60.0 dB SPL", f"{20e-6 * 10 ** (L / 20):.6f} Pa"),
        ("pressure of the full-scale sine", f"{20e-6 * 10 ** (Lfs / 20):.6f} Pa"),
        ("one pascal, in dB SPL", f"{20 * math.log10(1.0 / 20e-6):.4f}"),
    ]
    for name, value in rows:
        print(f"{name:<32}{value}")
    EOF
    peak amplitude                  0.019952623150
    root mean square                0.014108635132
    pressure at 60.0 dB SPL         0.020000 Pa
    pressure of the full-scale sine 1.002374 Pa
    one pascal, in dB SPL           93.9794

The last two lines are why 94.0 is a convenient reference and not a magic one.
One pascal is 93.9794 dB SPL, so a reference of 94.0 puts full scale a fortieth
of a decibel above one pascal. Rounding it to 94 is a choice each fixture makes
and states. Nothing here requires it, and a fixture is free to say 93.9794 or
anything else, which is the whole point of the reference being a field.

### Integers

Where the description asks for an integer bit depth, the amplitude above is
multiplied by the largest positive value the depth holds, which for sixteen bits
is 32767 and not 32768. The negative end of a two's complement range reaches one
step further than the positive end, and scaling by the larger number puts a
full-scale positive peak one step outside what can be stored.

Continuing the example, at sixteen bits:

    $ python -c "print(10 ** ((60.0 - 94.0) / 20) * 32767)"
    653.7876027458528

which is sample value 654 after rounding. That number is what a reader checks a
generator against by hand, and it is the reason this section states a bit depth
rather than leaving the mapping implied.

## The level convention for a modulated signal

Amplitude modulation changes the root mean square of a carrier, so a fixture
saying sixty decibels has to say sixty decibels of what. Both readings are in
circulation:

- the level of the unmodulated carrier, before modulation was applied
- the level of the modulated signal as produced

Every description of a modulated signal states which one it means. The field is
required and has no default, for the same reason the calibration reference has
none: a default is a convention nobody wrote down.

For sinusoidal amplitude modulation of depth `m`, where the envelope is
`1 + m * sin(2 * pi * fm * t)` and `m` runs from zero to one, the two readings
differ by

    10 * log10(1 + m ** 2 / 2)

decibels, with the modulated signal being the louder of the two. At three depths:

    $ python -c "import math; [print(f'm = {m:.2f}    {10 * math.log10(1 + m * m / 2):.6f} dB') for m in (1.0, 0.5, 0.25)]"
    m = 1.00    1.760913 dB
    m = 0.50    0.511525 dB
    m = 0.25    0.133640 dB

The first row is the one that matters, because full depth is what the roughness
and fluctuation strength anchors use. Reading it the wrong way round reports
every implementation as disagreeing by 1.76 dB of input level, in the same
direction, on exactly the fixtures the project's headline claims rest on.

That figure is derived rather than looked up, and it was checked against the
samples rather than trusted:

    $ python - <<'EOF'
    import math
    fs, fc, fm, n = 48000, 1000.0, 70.0, 48000
    car = [math.sin(2 * math.pi * fc * k / fs) for k in range(n)]
    mod = [(1 + 1.0 * math.sin(2 * math.pi * fm * k / fs)) * c for k, c in enumerate(car)]
    r = lambda x: math.sqrt(sum(v * v for v in x) / len(x))
    print(f"analytic {10 * math.log10(1 + 1.0 ** 2 / 2):.6f} dB")
    print(f"measured {20 * math.log10(r(mod) / r(car)):.6f} dB")
    EOF
    analytic 1.760913 dB
    measured 1.760913 dB

### Frequency modulation

A frequency-modulated sinusoid has a constant envelope, so its root mean square
is the carrier's and the two readings coincide. The field is still required on a
frequency-modulated description. A reader who has to know that fact in order to
interpret a fixture is a reader who can get it wrong, and a field that is
present on one kind of description and absent on another is a schema that has to
be explained.

## The reference anchors

Two signals are definitions rather than measurements, which is what makes them
safe to carry here and worth testing against.

One asper is the roughness of a 1 kHz tone at 60 dB SPL, amplitude modulated at
100 percent depth by a 70 Hz sinusoid.

One vacil is the fluctuation strength of the same carrier at the same level and
depth, modulated at 4 Hz instead.

Both come from the definitions the psychoacoustic literature states, not from a
table in a purchased document, and nothing in this file was transcribed from
one. Their level is stated under the carrier reading of the convention above.
The fixtures that carry them are issue #26; what is written here is the meaning
those fixtures are built against.

## What this does not settle

The fade at the onset and the offset. A sinusoid that starts at a non-zero
sample is a click, and a click is broadband energy the metric will see, so the
fade shape and duration are part of the stimulus and are stated by the
description. What the permitted shapes are belongs with the generator in #21.

The sample rate and the duration, which are explicit fields for their own
reasons and are not conventions anyone disagrees about.

The spelling of any of these fields. The schema is issue #24 and it is the
authority for what a description looks like. What is fixed here is what the
values mean, so that the schema can name them and this file does not have to be
read to know how a field is spelled.

Nothing enforces any of this. There is no generator, no schema and no check that
reads a description, so a fixture stating a level under the wrong convention
would be refused by nothing today. Issue #49 is where the invariants in this
file become rules that refuse.
