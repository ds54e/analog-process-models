# Post-v4 release maintenance

## Active task: APM v5.0.0 preflight

Status: **READY FOR CODEX EXECUTION; REAL-NGSPICE PREFLIGHT NOT YET RUN HERE**.

The user has explicitly authorized the bounded, offline v5 preflight described in
[`V5_PREFLIGHT.md`](V5_PREFLIGHT.md). This is a limited addition to the maintenance
scope below, not authorization to implement or release the complete v5 feature.
Follow the existing `AGENTS.md` policy, then that task specification and
`tools/v5_preflight/V5_MINIMUM_EXPERIMENT.md`. The repository owns the instructions
and prototype; no chat attachment or external ZIP is required.

Complete and report, independently for VTG N/P:

1. hierarchical application of raw variation to one isolated MOS;
2. maximum-gm extraction convergence;
3. two-observable mapping from artificial Delta Vth/beta targets to instance knobs;
4. the public-source beta-normalization audit, resolved or explicitly unresolved.

Only isolated preflight tooling/tests, new preflight reports, public-source audit
notes, and current task/status documentation may be developed in this phase. Keep
raw runs and fetched research documents under ignored `.apm/v5-preflight/` storage.
Exploratory report formats are allowed; they are not released public result schemas.
The minimum experiments do not use an approved measured beta coefficient.

Do not change `src/apm/`, released models/wrappers/manifests, existing Benchmark v2 or
native variation, historical validators, frozen records, tags/releases, or version
metadata just to make these experiments pass. Do not create a production Research
Variation API, new statistical profile, or full v5 release contract yet. Preserve
`4.0.0+main`. No author contact or external messaging is authorized.

Read `tools/v5_preflight/README.md` before running the supplied scaffold. Its offline
PASS is not real-SPICE evidence, and the experimental specification takes precedence
over its implementation. Repair the scaffold when justified by real evidence; do not
weaken the required experiment or silently substitute a different observable.

Finish when the feasible experiments and source audit are documented in
`validation/evidence/v5_preflight_findings.json`,
`validation/evidence/v5_preflight_source_audit.md`, and `STATUS.md`, with exact
identities and explicit failures or unresolved states. A useful negative finding may
complete preflight, but it is not a PASS for the failed experiment. Propose the smallest
full-v5 contract changes; do not activate full implementation or release automatically.

## Current state

APM v1.0.0 through v4.0.0 are released and immutable. The latest release is v4.0.0:

- annotated tag: `v4.0.0`;
- annotated-tag object: `797cdf9462db9dd634bff558802bcadaaeb70015`;
- tagged commit: `d224f279921c7e1ae637fd867e00d450067766c6`;
- pre-tag candidate qualification: 15/15 candidate-required gates PASS;
- exact-tag requalification: 16/16 required gates PASS;
- GitHub Release: `Analog Process Models v4.0.0`;
- historical evidence: `validation/evidence/v4_release_candidate.json` and
  `validation/evidence/v4_post_release_requalification.json`.

Current `main` is the post-v4 public-maintenance line. It is not a continuation
of v4 release execution and is not a replacement release target. The active bounded
preflight does not change that released baseline.

Its package identity remains `4.0.0+main`. Exact source identity uses the recorded
Git commit, worktree snapshot, and input hashes; the immutable v4.0.0 tag retains
plain `4.0.0`.

## Maintenance baseline

Keep the released APM portfolio usable, reproducible, and accurately documented,
preserving released electrical/noise behavior, model bytes, evidence, public schemas,
and claim meaning. Current APM045 positioning is defined by
[`APM045_POSITIONING.md`](APM045_POSITIONING.md); preserved contracts include
`DEVICE_FAMILY_MODEL.md`, `RESULT_CONTRACT.md`, and `NOISE_CHARACTERIZATION.md`.
The current interpretation is generic 40/45 nm-class, not a TSMC model or proxy.
Historical v4 45/55 nm-class wording is retained as history, not rewritten.

Ordinary maintenance may fix live documentation, tests, packaging, security, licensing,
provenance, and reproducibility defects within that boundary. Any work beyond the
explicit preflight scope requires a further user decision.

## Frozen release history

Do not edit `V4_MIXED_VOLTAGE.md`, `RELEASE_V4.md`,
`validation/release_gates_v4.toml`, `validation/release_review_v4.toml`, or
`validation/evidence/v4_*.json` to make current text agree with past phases.
Do not tune or regenerate the canonical released io18/io25 cards or wrappers.
Do not move, recreate, delete, or amend a released tag, tagged commit, or GitHub
Release; rewrite history; or force-push.

Post-tag evidence commit `02959d4a095062873fa2a3a53936af3cb4598ee3` remains the
single byte authority for the completed frozen scope: release documents/procedure;
v4 gate/review/comparison contracts; every `validation/evidence/v4_*.json`; the full
`tools/modelgen/apm045_mixed_voltage/` generation, qualification, calibration-replay,
and reconstruction history; v4 clean-clone/release-validator implementations;
`models/apm045/families/io18/` and `models/apm045/families/io25/`; and the APM045
technology, provenance, and evidence manifests. That commit descends from the tag;
it is not a different release target and does not supersede the tag.

The frozen `apm validate --release` and `apm validate --release-v4` retain their
original historical meaning. Ordinary current-tree validation uses unflagged
`apm validate` and must not update a historical release review to accept changed
live documentation.

## Change boundary

Outside the bounded exploratory preflight above, maintenance does not authorize a
new family, technology, operating profile, public schema, or release. It never
authorizes foundry/silicon calibration, yield, reliability, breakdown, lifetime,
safe-voltage, real-Spectre, calibrated leakage/GIDL/process-noise, layout-parasitic,
or physical interpretation of the model-construction ensemble as process variation.
No standalone io33 family or foundry design-rule interpretation is introduced.

A future change crossing these boundaries needs a new explicit goal and evidence
plan. Stop and report instead of altering a released artifact, rewriting history,
or changing released model/evidence semantics.

## Validation and evidence

Using the existing project-local environment, run the applicable checks:

```console
.venv/bin/apm doctor
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/reuse lint
.venv/bin/apm provenance-check --output .apm/results/provenance
.venv/bin/apm validate --output .apm/results/validation
```

Choose fresh output directories rather than overwriting results. Additionally run
the separate preflight test suite and real experiments specified in `V5_PREFLIGHT.md`.
Missing, skipped, unavailable, failed, or not-run checks are never passes. Record
preparation checks separately from reference-host execution. Update `STATUS.md` with
actual results, including blockers; do not leave an old PASS presented as validation
of a changed current tree.
