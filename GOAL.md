# APM v3 Noise Characterization Foundation Goal

## 0. Repository state

Work on the existing repository:

- repository: `https://github.com/ds54e/analog-process-models`
- project: Analog Process Models (APM)
- released baseline: `v2.0.0` at `3cc6cfea4932cc40f2d693784d0a569926cdf399`

APM v2.0.0 is complete, released, and immutable. Current `main` is the post-v2 development line.

Do not change repository visibility. Do not move/rewrite the v2 tag. Do not create/tag v3.0.0 as part of this goal.

## 1. Goal

Build and validate the **v3 stationary small-signal MOS-noise characterization foundation** and complete the required four-engine spike defined in `NOISE_CHARACTERIZATION.md`.

This goal is deliberately evidence-first. Do not jump directly to a full v3 release or tune new APM process-noise coefficients before the framework/harness/backend behavior is proven.

The main deliverable is a working, tested, machine-readable noise characterization path that demonstrates what the existing APM models actually predict and records where those predictions come from.

## 2. Preserve the v2 baseline

Do not redesign working v2 functionality merely because v3 is starting.

Keep the existing:

- Technology -> Electrical Family -> Device manifest architecture;
- Operating Profile and Backend Binding structure;
- public family-qualified device identities;
- planar `w,l` and FinFET `l,nfin` geometry semantics;
- canonical finite-difference gm/gds methodology;
- existing `apm.characterization.v2` result domain;
- v2 comparison/benchmark/native-variation behavior unless a narrow shared helper refactor is clearly justified.

Prefer a separate `apm.noise-characterization.v1` result domain.

## 3. Required reading and implementation authority

Follow `AGENTS.md` and `NOISE_CHARACTERIZATION.md` completely.

Treat `NOISE_CHARACTERIZATION.md` as the normative technical contract for this goal. When it deliberately leaves a value unfrozen, resolve it from real spike evidence rather than guessing.

## 4. Reuse the existing toolchain

First inventory the current local environment and reuse it when valid:

- WSL2 + AlmaLinux/RHEL-compatible EL9 x86_64;
- Python environment;
- ngspice 47 reference build;
- project-local OpenVAF-ReLoaded;
- existing PSP103 and BSIM-CMG OSDI build artifacts/caches.

Do not rebuild solved infrastructure without a reason.

If repair/rebuild is required, keep it reproducible and record the reason/evidence.

## 5. Implement an independent noise domain

Create a small dedicated implementation rather than growing `characterize.py` into a monolith.

Preferred responsibilities, names may differ if a smaller design is better:

- `noise.py` — operating-point resolution, fixture generation, ngspice execution, parsing, result persistence;
- `noise_fit.py` — optional spectrum fitting/derived metrics, with explicit invalid/failure status;
- `noise_validate.py` — analytic fixtures, four-engine spike validation, evidence generation.

Add CLI surface sufficient to run the spike and individual selectors, for example:

```text
apm noise <technology/family/device> --output ...
apm noise-check --output ...
```

Do not create a generic compact-model plugin system. Small engine-specific snapshot adapters are acceptable where parameter-provenance interrogation genuinely differs.

## 6. Validate the measurement harness before MOS devices

Implement and run, in order:

1. analytic resistor short-circuit noise reference;
2. CCVS/current-probe transparency check;
3. minimal APM-owned Verilog-A `white_noise` OSDI fixture;
4. minimal APM-owned Verilog-A `flicker_noise` OSDI fixture;
5. analytic APM-owned correlated internal-noise network through OpenVAF -> OSDI -> ngspice.

The correlated fixture must distinguish a correctly correlated result from an independent-source interpretation by a large deterministic ratio, not by visual inspection.

Persist fixture source, generated artifacts/hashes as appropriate, commands, tool identities, numerical expected/observed values, tolerances, and logs/evidence.

Use the normal Sparse solver for required `.noise` validation. Do not use KLU as the reference noise solver.

## 7. Implement precise equal-inversion bias resolution

For the canonical noise point, resolve:

- `gm/Id target = 15 1/V`;
- `VOUT = 0.5 * reference_vdd`;
- `L/Lmin = 2`;
- planar default width or FinFET `NFIN=1`;
- 27 degC.

Do not merely select the nearest old DC sweep row.

Use existing DC characterization as a bracket/prior, then re-run/refine the control bias and recompute canonical finite-difference gm/gds until the target is met within the provisional 1% relative error requirement or a real reachability failure is recorded.

Persist the complete target-resolution diagnostics.

## 8. Implement the canonical noise harness/result

Implement the candidate 1-ohm ideal transimpedance/current-probe approach from `NOISE_CHARACTERIZATION.md`, subject to the analytic probe validation.

Required canonical persisted quantities include:

- `s_idrain_terminal_a2_per_hz`;
- `s_vgate_equivalent_v2_per_hz`;
- complex external gate-to-measured-drain transfer (`y_dg_real_s`, `y_dg_imag_s`);
- the resolved DC operating point and finite-difference gm/gds;
- frequency profile/method identity;
- source breakdown when ngspice exposes it;
- complete noise-model/effective-parameter snapshot and provenance.

Do not call the APM canonical external result `sid`.

Use ngspice PSD rather than amplitude spectral density as the stored canonical numeric basis. Human-facing derived/display quantities may use square roots if clearly named.

## 9. Effective noise-parameter snapshot

For each of the four required engines, determine and persist the effective noise selectors/coefficients actually used by the simulation.

Distinguish:

- explicit upstream/model-card values;
- explicit APM values;
- compact-model defaults;
- backend-resolved defaults;
- values derived internally by the model;
- unknown/unresolvable values.

For native BSIM3/BSIM4, investigate ngspice model interrogation such as `showmod` as the preferred final-value source.

For PSP103/BSIM-CMG OSDI, experimentally determine whether backend interrogation is sufficiently complete. If not, implement a narrow engine-specific resolver based on the pinned vendored Verilog-A parameter declarations plus explicit model-card overrides.

Do not hardcode a universal raw compact-model parameter API.

## 10. Complete the four-engine spike

Required selectors:

```text
apm350/general/nmos
apm130/lv/nmos
apm045/vtg/nmos
apm016f/svt/nfet
```

Required provisional conditions:

```text
T = 27 degC
L/Lmin = 2
Planar W = family/device default
FinFET NFIN = 1
VOUT = 0.5 * reference_vdd
gm/Id target = 15 1/V
frequency = 1 Hz ... 100 MHz
20 points/decade
```

For every engine:

- real ngspice execution must complete;
- required PSD values must be finite/non-negative at retained points;
- gate-referred PSD and complex transfer must be persisted;
- source summaries must be captured when available;
- effective noise parameter/provenance snapshot must be produced;
- logs must be audited for unsupported/noise-specific/critical diagnostics.

Do not change APM350/APM022/APM016F noise coefficients to make the spike pass.

## 11. PSP and BSIM-CMG correlation handling

Do not assume OSDI correlated noise is supported or unsupported solely from the OSDI version number.

Use the analytic correlated-network fixture to establish what the current OpenVAF/OSDI/ngspice path actually preserves.

Inspect the pinned PSP/BSIM-CMG Verilog-A implementation as necessary to understand its internal-node correlation construction.

If the generic fixture passes, additionally exercise representative PSP/BSIM-CMG model modes and record what correlation claim is justified by real-tool evidence.

Do not enable/change production model selectors merely to obtain a desired result unless the selector is explicitly part of a separate diagnostic experiment and the baseline model remains unchanged.

## 12. APM130 native noise oracle investigation

Investigate PSP native operating-point noise quantities such as `sid` and `sfl` using the existing native-vector binding mechanism or a narrow extension.

Use them as validation oracles/trend evidence only when their semantics are established.

Do not demand equality between PSP internal/native channel quantities and the APM external drain-terminal total PSD.

Persist any oracle comparison and its semantic caveats.

## 13. Spectrum fitting is secondary to raw evidence

Persist raw spectra first.

Implement fitting only after the four-engine spectra exist. Candidate outputs include:

- flicker exponent;
- flicker coefficient;
- white floor;
- flicker corner;
- `gamma_eff_total`;
- explicitly band-limited integrated noise.

Do not silently choose a last-frequency point as a white floor or move fitting windows until something passes.

If a fit is not justified, persist explicit invalid/not-observed status and null derived metric.

Do not freeze final fit thresholds before the four-engine evidence is reviewed. If you implement provisional thresholds, label/version them provisional and make them easy to replace without changing the raw result contract.

## 14. Tests

Add unit/property/integration tests sufficient to prevent:

- FinFET fake-width regression;
- wrong gm/Id target resolution;
- probe sign/scale errors;
- accidental ASD/PSD unit confusion;
- source-breakdown names being treated as universal semantics;
- missing parameter-level provenance;
- silent fit fallback;
- KLU use in required noise jobs;
- OSDI correlation regression after the analytic fixture is established.

Keep existing v2 tests green unless a deliberate, documented shared-helper change requires a narrowly justified update.

## 15. Evidence and status

Create compact machine-readable evidence under `validation/evidence/` for the v3 spike.

Record in `STATUS.md`:

- spike implementation state;
- exact four-engine results;
- harness/correlation results;
- parameter-interrogation results;
- any unresolved decisions;
- explicit recommendations for the next v3 milestone.

Do not claim a full v3 release from this goal.

## 16. Decisions to make only after evidence

After the spike, use the results to decide and document, but do not guess beforehand:

- final required frequency range/points-per-decade;
- final white/flicker fit method/tolerances;
- the exact PSP/BSIM-CMG correlation-support claim;
- whether backend model interrogation or source parsing is authoritative per engine;
- whether one common frequency profile works for all 26 public devices;
- whether a low-VDS diagnostic profile should become required;
- whether the next phase should characterize all 26 devices;
- whether APM-authored generic noise coefficients should be researched for a later v3.1-style milestone;
- whether a full terminal noise-correlation matrix is worth a later extension.

## 17. Completion criteria

Do not stop at planning/scaffolding.

This goal is complete only when every initial-spike acceptance criterion in `NOISE_CHARACTERIZATION.md` is exercised with real evidence or a genuine blocker is documented.

A successful completion should leave the repository in this state:

```text
v2.0.0 release remains immutable and valid
+
working v3 noise domain
+
validated analytic noise fixtures
+
validated BSIM3 / PSP103-OSDI / BSIM4 / BSIM-CMG-OSDI spike
+
parameter-level noise provenance snapshots
+
explicit evidence-based list of what is ready for the next v3 milestone
```
