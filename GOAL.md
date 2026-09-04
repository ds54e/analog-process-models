# Post-v4 release maintenance

## Current state

APM v1.0.0 through v4.0.0 are released and immutable. The latest release is
v4.0.0:

- annotated tag: `v4.0.0`;
- annotated-tag object: `797cdf9462db9dd634bff558802bcadaaeb70015`;
- tagged commit: `d224f279921c7e1ae637fd867e00d450067766c6`;
- pre-tag candidate qualification: 15/15 candidate-required gates PASS;
- exact-tag requalification: 16/16 required gates PASS;
- GitHub Release: `Analog Process Models v4.0.0`;
- release evidence: `validation/evidence/v4_release_candidate.json` and
  `validation/evidence/v4_post_release_requalification.json`.

Current `main` is the post-v4 public-maintenance line. It is not a continuation
of v4 release execution and is not a replacement release target.

Its package identity is `4.0.0+main`, a PEP 440 local identifier for source
built from the post-release line. This is not a new release version. The exact
identity of a validated maintenance result is the report's Git commit,
working-tree snapshot, and input hashes; the immutable `v4.0.0` tag continues
to contain and report plain `4.0.0`.

## Goal

Keep the released APM portfolio usable, reproducible, accurately documented,
and safe to maintain without changing released model behavior, evidence, or
claim meaning.

The current APM045 portfolio and its claim boundaries are summarized in
[`APM045_POSITIONING.md`](APM045_POSITIONING.md). The preserved electrical,
result, and stationary-noise contracts remain
[`DEVICE_FAMILY_MODEL.md`](DEVICE_FAMILY_MODEL.md),
[`RESULT_CONTRACT.md`](RESULT_CONTRACT.md), and
[`NOISE_CHARACTERIZATION.md`](NOISE_CHARACTERIZATION.md).

## In scope

- correct live documentation that is stale, contradictory, or unclear;
- maintain tests, packaging, and ordinary current-tree validation;
- fix security, licensing, provenance, and reproducibility defects;
- fix implementation defects while preserving released public schemas,
  electrical/noise behavior, and model bytes;
- improve non-semantic diagnostics and maintenance ergonomics;
- record honestly which checks and real tools were actually run.

## Frozen release history

Completed v4 contracts, release procedures, review records, and evidence are
historical release records. In particular, do not edit
`V4_MIXED_VOLTAGE.md`, `RELEASE_V4.md`,
`validation/release_gates_v4.toml`,
`validation/release_review_v4.toml`, or `validation/evidence/v4_*.json` to make
current maintenance text agree with a past release phase. Their phase-specific
language remains historically correct.

The canonical released io18/io25 model cards and wrappers are also frozen.
Do not tune, regenerate, or replace them during maintenance. Do not modify,
move, recreate, or delete a released tag or GitHub Release; amend a tagged
commit; rewrite published history; or force-push.

Post-tag evidence commit `02959d4a095062873fa2a3a53936af3cb4598ee3` is the
single byte authority for this completed frozen scope. The maintenance audit
compares it with the release documents and procedure; v4 gate, review, and
mixed-voltage comparison contracts; every `validation/evidence/v4_*.json`;
the complete `tools/modelgen/apm045_mixed_voltage/` generation,
qualification, calibration-replay, and reconstruction history; the v4
clean-clone/release-validator implementations; the released
`models/apm045/families/io18/` and `models/apm045/families/io25/` trees; and
their APM045 technology, provenance, and evidence manifests. That commit
descends from the tagged release and adds final release evidence; it is not a
different release target and does not supersede the immutable tag.

The frozen `apm validate --release` and `apm validate --release-v4` workflows
retain only their original v3/v4 qualification meaning. Ordinary maintenance
must use unflagged `apm validate` and must not update a historical release
review merely to accept changed live documentation.

## Change boundary

Post-v4 maintenance does not authorize:

- a new electrical family, technology, operating profile, schema, or release;
- any change to model/electrical/noise semantics or existing evidence meaning;
- foundry/silicon correlation, manufacturable-PDK, yield, reliability,
  breakdown, lifetime, safe-voltage, or real-Spectre claims;
- calibrated leakage, GIDL, layout-parasitic, or process-noise claims;
- treating the retained io18/io25 model-construction ensemble as process,
  mismatch, yield, or foundry variation;
- a standalone io33 family or a foundry design-rule interpretation of tested
  model-supported geometry.

A future change that crosses this boundary needs a new explicit, versioned
goal and evidence plan. Stop and report if a requested cleanup would require
altering a released artifact, rewriting history, or changing released
model/evidence semantics.

## Validation

For a normal full maintenance change, run the project-local toolchain:

```console
.venv/bin/apm doctor
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/reuse lint
.venv/bin/apm provenance-check --output .apm/results/provenance
.venv/bin/apm validate --output .apm/results/validation
```

Run additional real-ngspice/OpenVAF/OSDI coverage when simulator orchestration,
models, or electrical/noise behavior is affected. A check that was skipped,
unavailable, or not actually run is not a pass. Update `STATUS.md` only after
the applicable validation has succeeded.
