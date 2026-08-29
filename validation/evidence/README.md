# Validation Evidence

This directory contains small, committed audit summaries for claims made during implementation and release validation.

It must not become a dump of raw simulator output.

## Status vocabulary

Use exactly these meanings:

- `validated` — the required real environment/tool/test ran successfully and directly supports the claim.
- `structurally_checked` — syntax/structure/static checks were performed, but the required real backend did not run.
- `experimental_unverified` — intentionally supplied without real-backend validation, as allowed by the project contract (notably Spectre v1.0).
- `blocked` — the required validation could not be completed; this is not a pass.

Absence of evidence is not a pass.

## Suggested evidence file naming

Use compact names tied to milestones or release gates, for example:

```text
m0-runtime.md
m1-apm130.md
m3-apm016f.md
variation-benchmark.md
apm130-native-variation.md
license-audit.md
clean-clone.md
release-validation.md
```

JSON may be used when tooling produces machine-readable summaries, but human-readable Markdown should remain sufficient to audit important claims without opening large generated files.

## Minimum evidence fields

Each evidence summary should include, where applicable:

```text
Gate / milestone:
Status:
Date:
Git commit:
Environment:
Tool versions:
Commands:
Exit codes:
Observed result:
Artifacts / hashes:
Limitations:
```

Do not paste huge logs. Include the relevant error/result excerpt or a concise summary and keep raw logs outside git.

## Real-tool evidence

For simulator/compiler claims, record actual version output and the command used to exercise the feature. A file existing on disk is not proof that a model loads or simulates.

For OSDI claims, evidence should distinguish:

1. Verilog-A source located and licensed;
2. compilation succeeded;
3. ngspice loaded the generated OSDI module;
4. an actual device simulation executed and produced sane output.

## Statistical evidence

For benchmark variation, do not rely on a single random sample.

Evidence should include automated checks for at least:

- same-seed reproducibility;
- different-seed difference;
- near-zero normalized sample means over an adequate cohort where appropriate;
- nonzero spread;
- intended process/global sharing semantics;
- intended mismatch/local independence semantics;
- `1/sqrt(match_size)` scaling behavior;
- `all` applying both process and mismatch perturbations.

Exact numerical snapshots are secondary; test documented statistical properties.

## Model-behavior evidence

For APM-authored models, evidence should tie behavior back to the documented contract rather than merely showing that ngspice converged.

Examples include:

- APM022 short-channel trends relative to APM045;
- APM016F NFIN current/gm scaling;
- APM016F improved electrostatic control relative to APM022;
- sensible capacitance trends;
- absence of obvious nonphysical discontinuities in supported characterization ranges.

## Licensing evidence

The final licensing audit should identify every vendored third-party asset and confirm:

- authoritative upstream URL;
- pinned revision;
- exact imported path;
- applicable license/redistribution terms;
- retained notices;
- checksum when useful;
- modifications, if any.

A repository-level license assumption is not enough when the imported file has its own terms or history.

## Spectre evidence

Without a real Spectre installation, Spectre evidence must remain `structurally_checked` or `experimental_unverified`.

Static checks may verify:

- expected model/wrapper files exist;
- expected APM public names are used;
- benchmark process/mismatch statistics structures are present;
- no prohibited Virtuoso helper layer was added;
- documentation labels the backend experimental/unverified.

Do not label these checks `validated Spectre compatibility`.

## Clean-clone evidence

The final `clean-clone.md` should be produced from a genuinely fresh clone, not by deleting build artifacts from the development tree.

It should record the clone commit, environment, documented setup commands, model build, `apm doctor`, full tests, release validation, and representative all-kit comparison results.
