# The quality parity map

## The target, and why it is the target

The target for this repository's quality gate is the gate that runs on the
jellyfin-plugin-sso board. It is public, so every claim made here about it can
be checked by whoever reads this. A parity claim against a private standard
would be unverifiable, and a parity claim against a general impression of good
practice is not a claim at all.

The board resolves as follows, and the map below was made against the commit
named here:

    $ gh api repos/iderex/jellyfin-plugin-sso --jq '.full_name, .visibility'
    Flowfin/jellyfin-plugin-sso
    public

    $ gh api repos/iderex/jellyfin-plugin-sso/commits/main --jq .sha
    fe7775a6ff52e5c33ad0108f68088c314a0637d1

The path in the issue that raised this, `iderex/jellyfin-plugin-sso`, redirects
to `Flowfin/jellyfin-plugin-sso`. Both reach the same tree; the second is what
the API reports and is what this document uses.

The target's gate, as it stands at that commit:

    $ gh api repos/iderex/jellyfin-plugin-sso/contents/.github/workflows --jq '.[].name'
    build.yml            codeql.yml               dco.yml
    dependency-review.yml dotnet.yml              e2e-login.yml
    fuzz.yml             manifest-freshness.yml   nightly-betas.yml
    opengrep.yml         pr-hygiene.yml           prettier.yml
    publish-beta.yml     publish-failure-alert.yml publish-jf12-beta.yml
    publish-jf12-stable.yml publish.yml           regenerate-manifest.yml
    scorecard.yml        stryker-mutation.yml     unicode-guard.yml
    wiki-lint.yml        zizmor.yml

The command produced one name per line; the layout above is column formatting
and nothing was dropped.

## What parity means here

Parity means the same kind of refusal, not the same tool. The other board is a
.NET plugin that authenticates users. This is a Python test harness that
compares numbers. Copying its checks verbatim would produce jobs that refuse
nothing here.

What transfers is the shape: analyser output as an error rather than a warning,
a coverage bar on the surface where a silent wrong answer does the harm,
mutation testing reported rather than enforced, invariants as lint rules, and a
fuzzing target on every parser that reads untrusted input.

## Parity already met

Five of the target's checks have run here since the first commit. That is
recorded as observed rather than assumed, and the observation is this:

    $ git ls-files .github/workflows
    .github/workflows/codeql.yml
    .github/workflows/dco.yml
    .github/workflows/dependency-review.yml
    .github/workflows/scorecard.yml
    .github/workflows/unicode-guard.yml
    .github/workflows/verify.yml
    .github/workflows/zizmor.yml

    $ gh run list --limit 30 --json name,conclusion --jq '[.[] | .name] | group_by(.) | map({name: .[0], runs: length}) | .[] | "\(.name)\t\(.runs)"'
    DCO                            3
    Dependency review              3
    Scorecard supply-chain security 4
    Workflow Security Analysis     8
    unicode-guard                  10

A tracked file proves a workflow exists; the run counts prove it has actually
executed, which is the part a reader should want. The names in that second
output are what the runs reported themselves as, quoted as evidence rather than
restated as a list this document maintains.

Two of the seven files are not among the five. `codeql.yml` is the static
analysis row of the map below, landed since. `verify.yml` is this repository's
own gate, which has no single counterpart on the target board and is not a
parity claim at all. The second output is a count taken on one day and it moves
with every run, including runs of those two, so re-run it rather than reading it
as current.

The five, matched by subject: the sign-off gate, dependency review, the
supply-chain self-audit, the Trojan Source character guard and the
workflow-security audit. Each has a counterpart file on the target board in the
listing above.

## The map

Every row states the deviation and the reason for it together. A row with no
reason does not belong in this document.

| The target's check | What it becomes here, and why it deviates | Delivered by |
| --- | --- | --- |
| Two target frameworks built and tested | Four interpreter versions, because the risk covered is the same one, a change that works on one runtime and not the other, and because this project declares four. The target board builds the two frameworks it claims; `classifiers` here claims 3.11 through 3.14, and a claim no run exercises is the thing this repository refuses everywhere else. Two ends of the range would have been cheaper and would have left two of those four claims unevidenced | #17 |
| Analyser warnings promoted to errors | The linter and the strict type checker run as gates, because this language has no compiler to promote warnings in, so the refusal has to come from tools run in refusing mode | #15 |
| Coverage bar on the security-decision surface | Coverage bar on the verdict surface, because the harm model differs: there a wrong answer lets someone in, here it publishes a false finding about somebody's work, so the surface is the comparator, the tolerance evaluation, the verdict mapping, the record writer and the report renderer | #47 |
| The coverage threshold number | Not copied. The same method is used instead, the bar set just below this project's own first honest measurement, because a number lifted from a project with a different surface is a number nobody chose and nobody will defend | #47 |
| Mutation testing, scored and reported | Identical posture, no deviation: scored, reported, never blocking on a low score, loud when the tool itself breaks. The posture is right for the same reason there as here | #48 |
| Invariant lint rules | The same mechanism with entirely different rules, because this project's invariants are its own: no expected value copied from a purchased document, no fallback from a licensed reference to a generated signal, no correction inside an adapter, no default tolerance | #49 |
| Static analysis into the code scanning view | Transfers directly, no deviation, because the tooling supports this language | #50 |
| Fuzzing the authentication parsers | Fuzzing with new targets, because the untrusted bytes enter elsewhere here: the fixture parser, the result record parser, the adapter result parser and the audio file reader | #51 |
| Architecture conformance tests carried inside the ordinary suite, as #52 records of that board | The same mechanism over this project's own structure, including the headless promise, because a structural rule left to a person to check is a rule that stops being checked | #52 |
| Pull-request hygiene and the artefact bill of materials | Transfers in form with a different artefact described, because what ships here is a Python distribution and a fixture set rather than a plugin package, and the hygiene half deliberately does not duplicate the sign-off gate because that gate is already at parity and two checks on one property are two things to keep in step | #53 |
| Scheduled end-to-end run against real providers | Transfers in purpose and not in subject: the fixture set against the real implementations. Scheduled rather than required in both places, because it depends on third parties whose availability is not this project's to guarantee | #54 |
| The format gate | Transfers directly, no deviation, with the formatter chosen in #15 and run in check mode in the gate | #15 |
| The license-header conformance test | Transfers, and is blocked. This repository has no license, so there is no header to conform to. See the section below | blocked on #1 |

Three rows point outside this milestone, one at #17 and two at #15. That is not
a gap in the map: the work exists, it is scheduled earlier, and pointing at a
milestone 6 issue that would only wait for it would be an invention.

## Deliberate absences

Three of the target's checks have no counterpart here, and the reason is the
same for all three: this project ships no plugin into a host application.

The publish pipeline checks, the manifest freshness check and the runtime floor
build are recorded as deliberate absences rather than as omissions. Milestone 8
says what this project's release checks are instead, and nothing here should be
read as a promise that they will eventually appear.

## The blocked row

The license-header conformance test cannot be built. This repository has no
license file, which in copyright terms means all rights reserved, so there is no
header text for a test to conform against and no way to write one that is not a
guess.

Its dependency is the first entry of issue #1, which is a maintainer decision
and is open. It is recorded here so that the absence is visible in the map
rather than discovered later by somebody wondering why the row is missing.

## Triaging what an analyser finds

Three of the checks in the map above report into the code scanning view rather
than failing a run, and the rule for what happens to what they report is the
same for all three.

Every finding is either fixed or dismissed with a written reason. A dismissal
with no reason is not a triage, it is a finding moved out of sight, and the
failure this prevents is the drawer of two hundred open alerts that everybody
has learned to scroll past. Once that drawer exists the view stops being read at
all, and the next real finding arrives into a place nobody looks.

A reason is a sentence about this repository and this code. "False positive" is
not one. "The query flags a subprocess call whose argument list is built from
constants in this file, and the fixture path never reaches it" is. Somebody
reading the dismissal a year later has to be able to tell whether it still
holds, and a reason that says nothing cannot be rechecked.

Dismissing a finding is a decision about risk, so it is made where decisions are
made here: on the issue that owns the check, or on a new issue where the finding
outlives the one that introduced it. The alert's own dismissal note carries the
same sentence, so a reader who arrives from the code scanning view is not sent
looking for it.

Nothing enforces this. No check counts open alerts, refuses a dismissal without
a note, or fails a run when the drawer fills up, and there is no open issue that
would add one. Read this section as a rule people follow rather than one the
tree refuses to break.

## What this document does not do

It does not enumerate this repository's checks. `docs/ci-checks.md` is the
authority for what runs here and what a failure of each one means, so that the
two cannot drift apart. It carries the check names; this document carries only
the issue that owes each row.

It does not claim parity is achieved. Five checks are at parity and the rest are
rows in a table pointing at open issues. A map is not a gate.

It does not verify the target board's internals. What was read from that board
is its visibility, its head commit and the names of its workflow files, by the
three commands quoted at the top. Everything in the left-hand column beyond
those names, including which checks live inside the ordinary suite rather than
in a workflow file of their own, comes from the issues that raised this map
rather than from reading that board here. A reader who wants those verified
should read them at the commit named above, which is why the commit is named.
