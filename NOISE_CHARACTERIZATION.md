# APM Noise Characterization — v3 Foundation

> **Released technical foundation / historical V3-N0 scope.** This document
> defined the V3-N0 spike and the external-terminal semantics preserved in APM
> v3.0.0. Its provisional spike questions were subsequently resolved by the
> frozen V3-N1/V3-N2 milestones. It remains a technical contract for the
> released foundation, but it is not the current implementation goal. See
> `README.md`, `STATUS.md`, and `AGENTS.md` for current state.
> APM v4 preserves these schemas and frozen method identities unchanged; its
> 30-device live-catalog extension and claim boundary are documented in
> `RELEASE_V4.md`. Historical references below to 26 devices describe v3 only.

This document defined the APM v3 noise-characterization foundation unless a
higher-authority repository policy overrode it.

APM v2.0.0 is an immutable released baseline. v3 adds a new characterization domain; it does not invalidate or silently redefine the validated v2 DC/Y/capacitance/result semantics.

## 1. Goal

Add reproducible, provenance-aware stationary small-signal MOS noise characterization across the existing APM catalog while preserving physically honest model-fidelity boundaries.

The central rule is:

> A noise analysis that executes successfully is not automatically a calibrated technology-noise model.

APM must distinguish:

- what the compact-model implementation can calculate;
- which effective noise parameters/selectors were actually used;
- where each effective parameter came from;
- what the ngspice/OSDI backend actually validated;
- what physical/calibration claims, if any, are justified.

## 2. Scope for the initial v3 spike

Required initial engines/devices:

- native BSIM3: `apm350/general/nmos`;
- PSP103 OSDI: `apm130/lv/nmos`;
- native BSIM4: `apm045/vtg/nmos`;
- BSIM-CMG OSDI: `apm016f/svt/nfet`.

Initial nominal condition:

- temperature: 27 degC;
- geometry: `L/Lmin = 2`;
- planar width: family/device default width;
- FinFET: `NFIN = 1`;
- effective output/drain bias: `VOUT = 0.5 * reference_vdd`;
- target inversion: `gm/Id = 15 1/V`;
- provisional spectrum: 1 Hz to 100 MHz, 20 points/decade.

The frequency range is provisional until the four-engine spike demonstrates that it is numerically useful across all four model engines.

## 3. Explicit non-goals for the spike

Do not add or tune APM-authored flicker/thermal noise coefficients during the initial spike.

Do not add:

- transient noise;
- RTS/random-telegraph models;
- PSS/PNoise;
- oscillator phase noise;
- RF noise figure/NFmin as a required metric;
- a canonical four-terminal noise-correlation matrix;
- Benchmark Global/Local/All noise variation;
- noise-coefficient mismatch/correlation models;
- IHP native noise Monte Carlo;
- Spectre numerical noise validation;
- new process/family/device models.

Do not change repository visibility.

## 4. v2 compatibility boundary

Keep the existing v2 characterization/result domain intact.

Preferred schema relationship:

```text
APM package v3.x
  apm.characterization.v2      # existing DC/Y/C domain
  apm.noise-characterization.v1 # new noise domain
```

Do not rewrite the validated v2 result schema merely to add noise.

Reuse the existing manifest-driven `Technology -> Electrical Family -> Device` identity, Operating Profiles, geometry semantics, backend bindings, provenance hashes, and gm/Id finite-difference machinery where appropriate.

## 5. Noise-parameter provenance is parameter-level

A single family-level `noise_origin` field is insufficient.

For every effective noise selector/coefficient that materially controls the result, persist at least:

- canonical/raw parameter name;
- effective numeric/string value;
- role, such as flicker selector, flicker coefficient, thermal selector, induced-gate selector, resistance-noise enabler;
- `value_source`;
- `origin`;
- method used to resolve the effective value.

Recommended `value_source` values:

- `explicit_model_card`;
- `explicit_apm_card`;
- `compact_model_default`;
- `backend_resolved_default`;
- `derived_by_model`;
- `unknown`.

Recommended `origin` values:

- `upstream`;
- `apm`;
- `bsim3`;
- `bsim4`;
- `psp103`;
- `bsim_cmg`;
- `backend`;
- `unknown`.

Do not collapse a family to `upstream_explicit` when only selectors are explicit and coefficients are compact-model defaults.

## 6. Existing model audit that must be preserved

### APM130

The pinned IHP PSP cards contain explicit family-specific noise parameterization such as `FNTO`, `NFALW`, `NFBLW`, `NFCLW`, `EFO`, and `LINTNOI`. PSP source implements channel/gate-correlated noise, flicker noise, gate shot noise, junction noise, and related contributions.

Treat this as `upstream-explicit parameterization`, not automatically as a claim of complete silicon-calibrated noise accuracy unless authoritative evidence supports that stronger claim.

### APM045

The pinned FreePDK45 BSIM4 cards explicitly select modes such as `FNOIMOD=1` and `TNOIMOD=0`, while some noise coefficients may come from BSIM4 defaults.

Persist the mixed provenance instead of calling the entire noise model explicit.

### APM350 / APM022 / APM016F

Current APM-authored cards do not intentionally calibrate process-specific noise coefficients.

If native BSIM3/BSIM4/BSIM-CMG default parameters produce a valid spectrum, describe it as compact-model-default prediction unless/until APM creates an evidence-backed generic noise target/calibration in a later phase.

For APM016F specifically, the vendored BSIM-CMG 112.1.0 implementation contains substantial default flicker/thermal/correlated-noise machinery. This does not make the APM016F deck a calibrated 16 nm process-noise model.

## 7. Backend capability and fidelity are distinct

Persist backend execution/capability information separately from parameter provenance.

Recommended concepts:

- `noise_backend_validation`: `not_tested`, `structural`, `real_tool`;
- `noise_correlation_path`: `none`, `model_internal_network`, `native_backend`, `unknown`;
- `source_breakdown_available`: boolean;
- `effective_parameter_snapshot_available`: boolean.

A family may have `compact_model_default` noise parameters and still have `real_tool` backend validation.

## 8. Canonical external observable

Do not use the ambiguous field name `sid` for the APM canonical result. PSP and BSIM-CMG already use `sid` internally/native-operating-point semantics.

Canonical primary quantity:

`s_idrain_terminal_a2_per_hz`

Definition:

> Total stationary small-signal short-circuit noise-current PSD entering/leaving the external drain terminal according to the recorded APM sign convention, with external D/G/S/B terminal voltages fixed by ideal noiseless voltage sources at the recorded DC operating point.

Store PSD as a non-negative magnitude. Preserve raw/backend sign/source conventions separately where relevant.

This external-terminal total may include any model-enabled intrinsic channel, flicker, gate-current shot, junction, series-resistance, gate-resistance, and correlation effects. It is not identical to an internal channel-thermal `sid` variable.

Secondary canonical quantity:

`s_vgate_equivalent_v2_per_hz`

Definition:

> The same output/drain-terminal noise referred to the external gate excitation using the actual small-signal gate-to-drain transfer of the measurement fixture/backend.

## 9. ngspice current-noise harness

Initial harness candidate:

```spice
Vd d 0 DC <vd>
Vg g 0 DC <vg> AC 1
Vs s 0 DC 0
Vb b 0 DC 0

Xd d g s b <APM_PUBLIC_DEVICE> <geometry>

* Convert Vd branch current to voltage with ideal 1-ohm transresistance.
HNOISE nout 0 Vd 1

.control
set sqrnoise
noise v(nout) Vg dec 20 1 100MEG 20
.endc
```

The 1-ohm CCVS is only a candidate until validated by the reference fixtures below.

Noise jobs must use the normal Sparse solver path. Do not use KLU for required `.noise` validation because ngspice documents KLU noise-analysis incompatibility.

## 10. Harness reference validation comes before MOS validation

Implement small deterministic fixtures and evidence before accepting MOS results.

### 10.1 Analytic resistor reference

Use an ideal resistor with known temperature and resistance. Verify the measured short-circuit current-noise PSD against:

`4*k*T/R`

at representative frequencies.

### 10.2 Probe transparency

Verify that inserting the candidate CCVS probe:

- does not change the DC operating point;
- does not change the expected resistor noise beyond tight numerical tolerance;
- introduces no independent noise source.

### 10.3 OSDI white-noise fixture

Create a minimal APM-owned Verilog-A fixture using `white_noise`, compile it with the existing OpenVAF-ReLoaded/OSDI path, and verify analytic amplitude through ngspice.

### 10.4 OSDI flicker-noise fixture

Create a minimal `flicker_noise` fixture and verify both amplitude and log-log frequency exponent.

### 10.5 OSDI correlated-network fixture

Do not infer correlated-noise support only from the OSDI specification version.

Create an analytic Verilog-A internal-node correlation network in the style used by PSP/BSIM-CMG. Construct a case where correlation predicts a clearly different output PSD from an independent-source interpretation, and verify the expected correlated result after OpenVAF -> OSDI -> ngspice.

Use this evidence to decide whether BSIM-CMG `TNOIMOD=1`/PSP internal correlation networks may be validated in the current reference flow.

## 11. gm/Id operating-point resolution

Do not reuse the v2 comparison behavior of simply selecting the nearest pre-existing gm/Id sweep row for the canonical noise point.

For each requested gm/Id target:

1. use existing DC characterization to bracket the target where possible;
2. interpolate a candidate effective gate/control bias;
3. re-run DC at that bias;
4. recompute canonical finite-difference gm/gds with the existing convergence method;
5. refine with a bounded secant/bisection-style iteration if needed;
6. persist target, achieved value, error, iteration count, bracket, and final bias.

Required anchor target:

`gm/Id = 15 1/V`

Provisional required acceptance:

`abs(achieved-target)/target <= 0.01`

If a requested auxiliary target is not reachable within the family's legal/characterized bias range, persist `target_not_reachable`; do not silently clip to an endpoint.

Candidate auxiliary 27 degC targets for later characterization:

`5, 10, 15, 20, 25 1/V`

Only the spike anchor `15 1/V` is required before the frequency/profile decisions are frozen.

## 12. AC transfer audit

In parallel with the noise run, preserve the complex small-signal transfer from external gate voltage excitation to measured external drain current/CCVS output.

Persist:

- `y_dg_real_s`;
- `y_dg_imag_s`;
- magnitude/phase may be derived.

At sufficiently low frequency, verify consistency with canonical DC finite-difference gm within a documented tolerance.

Do not use `S_id/gm^2` as the sole definition of input-referred noise over the full frequency range; at higher frequency the actual complex transfer includes capacitance and other dynamics.

## 13. Result contract — `apm.noise-characterization.v1`

Preferred per-run artifacts:

### `metadata.json`

Must include:

- schema/version/status;
- technology/family/device identity;
- public device name/polarity;
- operating-profile identity and resolved data;
- geometry;
- temperature;
- exact resolved bias and gm/Id target/achieved diagnostics;
- simulator/toolchain identity;
- manifest/binding/provenance hashes;
- frequency profile/method version;
- fixture/probe method/version;
- solver identity;
- model/parameter snapshot hashes;
- backend validation/capability flags;
- variation identity (`none`/`nominal` for the initial v3 scope).

### `operating_points.csv`

At least:

- `operating_point_id`;
- `technology_id`, `family_id`, `device_id`;
- temperature;
- geometry (`w_m,l_m` or `l_m,nfin`);
- effective/raw terminal biases;
- `idmag_a`;
- `gm_s`;
- `gds_s`;
- `gm_over_id_per_v`;
- gm/Id target/error/resolution status.

### `noise_spectrum.csv`

At least:

- `operating_point_id`;
- `frequency_hz`;
- `s_idrain_terminal_a2_per_hz`;
- `s_vgate_equivalent_v2_per_hz`;
- `y_dg_real_s`;
- `y_dg_imag_s`.

### `noise_metrics.csv`

Derived metrics and explicit fit status/window/quality. Do not populate invalid metrics with fabricated fallback values.

### `source_breakdown.json`

Raw backend/model-specific noise-generator summaries when available. Preserve source names; do not force PSP/BSIM/CMG source names into a false universal mapping.

### `noise_model_snapshot.json`

Parameter-level effective values and provenance for all materially relevant noise selectors/coefficients discovered for that model engine/family.

## 14. Effective parameter resolution

For native BSIM3/BSIM4, investigate ngspice `showmod`/model interrogation as the preferred way to capture backend-resolved final parameters, including defaults not written in the input card.

For OSDI PSP103/BSIM-CMG, determine experimentally whether equivalent model-parameter interrogation is complete enough. If not, use a clearly documented engine-specific resolver from the vendored Verilog-A parameter declarations plus explicit model-card overrides.

Do not hardcode a large universal compact-model parameter API into APM. Use small model-engine-specific snapshot adapters only for provenance/audit of noise parameters.

## 15. Source breakdown is evidence, not canonical physics mapping

Use ngspice noise summaries when available and retain raw generator names.

Examples may include model-specific names such as PSP `idid`, `flicker`, `igs`, `igd` or BSIM-CMG `id`, `1overf`, `corl`.

Do not claim cross-engine equivalence merely because names sound similar.

The common cross-family/cross-engine metric remains the external-terminal total PSD and gate-referred PSD.

## 16. Derived metrics and fitting

Primary truth is the persisted spectrum. Derived fitting must be fail-closed.

Candidate derived metrics:

- `flicker_alpha`;
- `flicker_fit_coefficient`;
- `white_floor_a2_per_hz`;
- `flicker_corner_hz`;
- `gamma_eff_total`;
- explicitly band-limited integrated drain-current noise;
- explicitly band-limited integrated gate-referred noise.

Define:

`gamma_eff_total = S_idrain_terminal_white / (4*k*T*gm)`

The name must retain `_eff_total`; do not confuse it with a compact-model intrinsic channel-noise gamma.

Initial fitting candidate:

- inspect local log-log slope;
- require a documented minimum contiguous frequency span/point count;
- white region candidate: approximately flat log-log slope;
- flicker region: OLS on `log(S)` versus `log(f)`;
- compute corner only when both fits are valid and overlap/intersection is meaningful.

Do not freeze numeric slope/fit thresholds before the four-engine spike. Persist the raw spectrum so methods can be changed without rerunning the simulator when possible.

## 17. Temperature and geometry after the spike

Do not make the full matrix a prerequisite for the initial four-engine spike.

After the harness/frequency/method decisions are frozen, planned v3 coverage is:

- all 26 public devices at the canonical gm/Id anchor and -40/27/85/125 degC;
- 27 degC gm/Id curve at selected targets;
- planar length/width scaling with native `w,l` semantics;
- FinFET length/NFIN scaling with native `l,nfin` semantics;
- no fabricated FinFET effective width;
- no cross-basis planar-per-width versus FinFET-per-fin ratio unless a later explicit physical conversion model is introduced.

## 18. Multi-Vt interpretation

APM022 LVT/SVT/HVT share the same APM-authored base except for the documented threshold-isolated VTH0 changes. APM016F LVT/SVT/HVT share the same basis except for the documented PHIG-only changes.

Therefore v3 may intentionally show how noise changes between those controlled generic families under:

- equal bias; and
- equal inversion/gm/Id.

Do not generalize the result into a claim that real foundry LVT/SVT/HVT families share identical noise parameters. Public PDKs demonstrate that real Vt flavors may have separately fitted noise coefficients.

## 19. APM130 native noise oracle

Investigate PSP native operating-point quantities such as `sid` and `sfl` as validation oracles.

Do not require direct equality between PSP internal/native `sid` and APM external drain-terminal total PSD: they are not necessarily the same physical quantity once correlated induced-gate noise, shot noise, junction noise, or parasitics are enabled.

Use native values to cross-check sign, finiteness, magnitude/trend, source decomposition, and low-frequency/white behavior where semantics are known.

## 20. Spike acceptance criteria

The initial spike is complete only when all of the following are evidenced with real ngspice on the existing reference toolchain:

1. analytic resistor noise reference passes;
2. candidate drain-current probe is transparent and noise-free;
3. OSDI white-noise fixture passes;
4. OSDI flicker-noise fixture passes;
5. OSDI correlated-network fixture has a decisive expected result;
6. gm/Id=15 anchor bias is resolved and revalidated for all four engines;
7. each of BSIM3, PSP103 OSDI, BSIM4, and BSIM-CMG OSDI completes the provisional noise spectrum;
8. drain-terminal PSD is finite and non-negative across the retained frequency points;
9. gate-referred PSD and complex gate-to-drain transfer are persisted;
10. source breakdown is captured when the backend exposes it;
11. an effective noise-parameter snapshot/provenance report exists for every engine;
12. simulator logs are audited for critical/unsupported/noise-specific diagnostics;
13. no APM-authored process-noise coefficient is modified merely to make the spike pass.

## 21. Decisions that remain deliberately unfrozen until spike evidence

Do not guess these before the four-engine evidence exists:

- final v3 required frequency range and points/decade;
- exact white/flicker fitting thresholds;
- final correlation-support claim for PSP/BSIM-CMG OSDI;
- which OSDI parameter-interrogation mechanism is reliable enough for the result contract;
- whether all 26 devices can share one required frequency profile;
- whether a separate low-VDS diagnostic profile becomes required;
- whether APM-authored generic noise coefficients should be developed in v3.1 or later;
- whether a future full terminal noise-correlation matrix is worth adding.

## 22. Evidence and claims

Store compact auditable spike evidence under `validation/evidence/` with hashes and exact tool/model identities.

A successful spike establishes simulator/framework capability and characterizes the current model predictions. It must not be described as silicon correlation for APM-authored generic families.

Do not modify the immutable `v2.0.0` tag or its release evidence. Do not create/tag `v3.0.0` from the spike alone.
