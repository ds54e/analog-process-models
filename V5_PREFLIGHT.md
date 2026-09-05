<!-- SPDX-FileCopyrightText: APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5.0.0 preflight: repository instructions for Codex

## Mission and authority

Execute the limited preflight authorized by `GOAL.md`. APM v5.0.0 is the intended
future release, not the completion criterion for this task. Complete the experiments,
source audit, and decision report before proposing the full implementation contract.

Read in order: `AGENTS.md`, `GOAL.md`, this file, `APM045_POSITIONING.md`,
`ENVIRONMENT.md`, `tools/v5_preflight/V5_MINIMUM_EXPERIMENT.md`,
`tools/v5_preflight/source_audit.toml`, and `STATUS.md`.
Preserved electrical, result, noise, provenance, and security contracts still apply.
This document and the minimum-experiment specification govern the exploratory code;
passing that code's existing tests is not proof of compliance with the specification.

Everything needed to start is in this repository. Do not require a chat attachment,
an external handoff directory, or the earlier ZIP. The English launch prompt is
`tools/v5_preflight/CODEX_PROMPT.md`.

## Authorized work and boundaries

You may review, repair, and extend the isolated tools and tests under
`tools/v5_preflight/`, investigate legitimate public sources, run real ngspice on the
existing reference host, and commit concise findings. Reuse the installed APM Python
and ngspice 47 environment; inspect it before bootstrapping anything.

Do not change released model cards, wrappers, model/family manifests, benchmark-v2
coefficients or semantics, IHP-native variation, frozen v4 modelgen/release files,
existing tags, tagged commits, GitHub Releases, or history. Keep package identity
`4.0.0+main`. No force push, new release, new tag, production Research Variation API,
public statistical profile, or v5 release validator is authorized in this preflight.
Do not contact authors or send external messages without separate authorization.

Use ignored `.apm/v5-preflight/` paths for PDFs, simulator decks, raw curves, logs,
cache, and large output. Record URLs, exact versions, hashes, page/table references,
and your own summaries; do not commit third-party papers, private PDKs, credentials,
or redistribution-unclear material. No commercial TSMC PDK is assumed or required.

## Intended v5 direction, not yet a runtime feature

Preserve Benchmark v2 and IHP-native variation as independent systems. The future v5
focus is APM045/VTG N/P local Vth/current-factor mismatch constrained by public
neighbor-process measurements. io18/io25 Vth transfer remains a separately labeled
hypothesis evaluation, not measured IO statistics. Do not fill missing IO beta,
Research Global/All, weak-inversion, spatial, layout, passive, aging, or noise
statistics with invented defaults. APM045 stays a generic 40/45 nm-class environment,
not a TSMC40/45 model or TSMC55 proxy.

## Work sequence

### 1. Establish the actual starting state

Record current HEAD, branch, worktree state, Python/package identity, ngspice binary
path/version/hash, and the three VTG input identities. The comparison baseline is
`b09d104759296e6dd59c6f08e6cd30fa716d6461`; it is not a request to reset or check out
old source. Preserve user changes and reconcile unexpected upstream commits.
Run `apm doctor` and the offline preflight tests. A missing tool is NOT_RUN, not PASS.

### 2. Prove hierarchical instance isolation

Start with W=1um, L=0.12um, 300K, |VDS|=50mV, separately for N and P.
Use the independent-twin hierarchical fixture in the minimum-experiment document.
Apply a nonzero DELVTO/MULU0 change to A only, read back W/L and both raw values
for A/B, and compare the untouched B curve with its nominal curve.

The bad-path and reset-after-apply controls must fail for their intended reason.
A generic solver error, missing output, or unrelated extraction failure is not a
successful negative control. Inspect and repair the supplied scaffold if it conflates
these cases. Prove application independently of MG extraction: an MG failure must not
prevent you from reporting whether instance application itself worked.

### 3. Prove maximum-gm extraction repeatability

Use the defined positive control-voltage/current coordinates and terminal-current
sweeps, not native BSIM VTH0 or a silent constant-current substitution. Run the
5mV/2mV/1mV grid-refinement experiment and inspect endpoint/competing-peak behavior.
Do not exceed the VTG profile voltage to manufacture an interior peak.

### 4. Prove the two-observable mapping

Measure a scaled Jacobian for (DELVTO, ln MULU0) to (Delta VTH_MG, Delta beta/beta0).
Test all four artificial combinations of +/-10mV and +/-2%, then remeasure with a
0.5mV gate grid. These are numerical test inputs, NOT manufacturing sigmas.
Use finite physical increments rather than optimizer machine-epsilon differencing.
Preserve cross terms, conditioning, residuals, and failed target cases.

Run both polarities even if one fails, unless a common environment problem prevents
meaningful execution. Keep separate statuses for application, extraction, and mapping.
Only expand to W=1/2/4um and L=0.12/0.24/0.40um after the initial point is understood.
Expansion failure cannot erase the initial result or silently redefine the scope.

### 5. Pursue the source audit in parallel

The Hart 2020 beta table normalization is an unresolved lead, not a runtime input.
Recheck the actual PDF plots, units, equations, pair/individual convention, geometry,
extraction method, and temperature. Inspect the first author's 2022 thesis when
accessible. A metadata page alone does not resolve a numerical inconsistency.

Accept a coefficient only with an auditable correction, an independently consistent
primary source, or explicitly documented reanalysis with uncertainty and independent
cross-checks. Do not silently divide by ten, treat synthetic test inputs as data, or
claim an author correction from your own inference. Keep unresolved values blocked.
Source uncertainty does not block the artificial software experiments.

## Review the imported scaffold before relying on it

The supplied Python tests were executed outside the WSL2/EL9 reference environment;
the ngspice path was not executed during preparation. The runner is editable
exploratory scaffolding, not a release gate. Specifically review failure classification,
per-polarity/per-experiment reporting, timeouts/log preservation, source/tool identity,
and readback semantics. Repair only what the experiment needs, add focused tests, and
record before/after evidence rather than building a generic framework first.

Preliminary numerical bounds/tolerances may be revised when evidence warrants it.
Record the original failure, rationale, revised method, and affected reruns. Do not
weaken a legitimate test merely to turn a failure into PASS. Changes to measurement
meaning, required scope, released artifacts, or source-adoption rules require reporting
and a decision, not silent substitution.

## Evidence and completion

Write compact, new records under `validation/evidence/`:

- `v5_preflight_findings.json`: exact source/tool identities, tested geometry,
  application/readback/isolation results, controls, extraction convergence, scaled
  Jacobians, mapped/recovered targets, failed cases, run counts, and raw-output paths;
- `v5_preflight_source_audit.md`: adopted versus blocked source facts, visual
  inspection references, and the beta decision or remaining ambiguity;
- a concise `STATUS.md` update after the actual work, distinguishing current results
  from prior post-v4 maintenance evidence.

The preparation record `v5_preflight_preparation.json` is NOT ngspice evidence and
must not be relabeled as execution evidence. Keep it as the preparation snapshot.
For new reports use explicit PASSED, FAILED, UNRESOLVED, NOT_RUN, or BLOCKED states;
never synthesize a green overall release status from missing subresults.

Run the ordinary repository checks applicable to changed files, the separate
`tools/v5_preflight/tests` suite, real `apm doctor`, Ruff, REUSE, provenance, and
unflagged `apm validate` using the existing toolchain. Do not rerun old release
workflows for decoration. Record checks that cannot run honestly. Verify the v4 tag
and protected model/history scope remain unchanged. Commit and push coherent work
using normal fast-forward history only; leave unrelated user changes untouched.

This task ends with the preflight findings and the smallest evidence-backed proposal
for the full v5 goal. A technically demonstrated negative outcome is a useful completed
preflight result, not proof that the experiment passed. Do not stop at offline tests
if real experiments can still run, and do not advance automatically to a v5 release.

Report these decisions separately:

1. hierarchical instance application: proven or unresolved;
2. MG extraction: proven or unresolved, with its tested domain;
3. two-observable mapping: proven or unresolved;
4. beta source normalization: resolved or unresolved;
5. next v5 contract changes: justified by the evidence, not implemented by default.
