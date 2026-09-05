<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v5.0.0 technical contract: Research Local Mismatch

Contract status: active implementation specification, not execution evidence.
Baseline: `bbb585306f13614b7649c36dd5b7510c845daed9`.
Gate index: `validation/release_gates_v5.toml`.
Source registry: `variation/research/apm045/sources.toml`.

## 1. Scope and interpretation

Add an optional local Vth/current-factor path for APM045/VTG N/P, independently
of Benchmark v2 and APM130-native variation. No nominal electrical family is
added; the catalog remains 15 families / 30 public MOS devices. Public W/L and
D/G/S/B interfaces remain unchanged. Statistics are transferred from an audited
neighbor-process source to a generic 40/45 nm-class model.

The deliverable is a working sample/apply/run/replay flow, not just coefficient
files. It must support a user-owned hierarchical circuit, an explicit instance
map and an authored analysis recipe. It need not become a general SPICE parser,
EDA workflow engine, distributed database or optimization framework.

Required: VTG N/P quantitative local Vth AND beta; sample persistence;
reference-condition mapping; hierarchical application; statistical and circuit
qualification; actual toolchain provenance; release-ready reproducibility.

Assessment-only: io18/io25 Vth transfer. Unresolved-with-evidence is an allowed
assessment outcome, not a passing numeric profile. VTL/VTH/THKOX and all other
technologies have explicit unsupported research capability unless a later goal
expands scope. Existing Benchmark/native functionality remains available.

Excluded: Research Global/All, automatic hybrid variation, physical yield,
foundry correlation, standalone io33, statistical passives, WPE/STI/spatial fields,
RTN/aging/transient-noise, calibrated SS or cryogenic variation, layout extraction,
and numerical Spectre claims. Do not implement empty frameworks for them.

## 2. What the completed preflight established

The historical findings record native ngspice 47 experiments at 300 K,
|VDS|=50 mV, VBS=0, W=1/2/4 um and L=0.12/0.24/0.40 um, both polarities.
Application/isolation, MG grid convergence and 72 artificial +/-10 mV,
+/-2% target combinations passed. Scaled condition numbers were approximately
4.16-4.85. Extremely small inverse-fit residuals are numerical self-consistency,
not silicon accuracy, measured statistics or proof of a broad stochastic domain.

Bad-path commands could return exit code zero; diagnostics and readback detected
the failure. Reset discarded applied parameters. The host's system spinit selected
8 threads; explicit `set num_threads=1` repaired oversubscription. Preserve those
negative findings and use them as regression cases, not merely prose.

Preserve `V5_PREFLIGHT.md`, `tools/v5_preflight/`, and the preflight preparation,
findings and source-audit records at this baseline. Develop production code and
new evidence separately. Do not relabel old artificial results as source-qualified.

## 3. Source adoption is a real release dependency

### 3.1 Separate the source families

The original Hart paper, DOI 10.1109/JEDS.2020.2976546, and its thesis reprint
have an unresolved beta table/plot/normalization inconsistency. Keep their N/P
beta values blocked. A factor-of-ten edit, unit guess, sqrt(2) conversion or fit
to APM cannot resolve a publication inconsistency by itself.

Prioritize the companion paper, DOI 10.1109/JEDS.2020.2988730, as an independent
source candidate. Its Sec. II explicitly distinguishes its process from the
original; the preflight thesis audit identifies ST40 LVT versus TSMC40 standard-Vt.
Do not silently combine ST Vth with TSMC beta. A default profile must use a
coherent paired Vth/beta source set; cross-process mixtures may be described as
unapproved sensitivity hypotheses only and cannot satisfy the source gate.

The companion reports ELR extraction and plots room-temperature beta with clear
percent axes. That is a promising lead, not permission to read off one number.
Reconcile Fig. 2's geometry inventory, Figs. 8/9's fixed-L slopes, Figs. 10/11's
length legends, and the room-temperature current-mismatch figures. In particular,
the long-L legend and 400 nm text/captions must not be silently equated.

Names alone do not establish that MG and ELR are equivalent OR different.
Read the referenced extraction definition, identify tangent/peak/smoothing and
VDS/2 conventions and beta normalization, compare algorithms on identical curves,
and document the transfer. The preflight method remains its own versioned APM
coordinate. Any justified additional extractor gets its own method ID; do not
silently change previously saved observables.

### 3.2 Required evidence for adoption

For each coefficient record: DOI/URL, exact file SHA-256, process identity as
stated or attributed, page/figure/table, polarity, flavor, voltage class,
temperature, VDS/VBS, W/L definition, number of pairs, extraction method,
statistic/denominator, reported units, normalized units, and uncertainty.
Distinguish pair mean, population mean and nominal normalization. Keep source
confidence intervals separate from digitization uncertainty and between-process
transfer uncertainty. A published 95% interval is not a per-device distribution
or a posterior to sample independently for each transistor.

Adopt via unambiguous primary tables/data, a verified correction, or auditable
figure reanalysis. For reanalysis, save axes calibration, points, uncertainty,
method and reanalysis script; use vector geometry when available and visually
verify it. Avoid OCR for numerical figures. Cross-check fit slopes against another
figure and predicted current mismatch against independent source observations.
A second fit of the same pixels is not independent confirmation. Never fit APM
nominal curves to fabricate the missing coefficient. Never claim digitized values
are author-issued corrections or raw measurements.

No silent latest-web input at runtime: pin approved numeric data locally with
source and method hashes. Respect file-level rights; retain third-party notices
and a separate appropriate license for adapted datasets when required. Do not
commit complete papers or screenshots merely because they are downloadable.
No author contact, external messaging or paid access is authorized.

### 3.3 Coefficient versus model validation

Three distinct checks are mandatory: source arithmetic/meaning; re-extraction of
configured statistics from the APM implementation; and cross-bias/circuit behavior.
Recovering coefficients from one's own sampler proves implementation, not silicon
calibration. Output and documentation must preserve this distinction.

If no coherent source passes, leave runtime profiles unapproved. Continue all
independent implementation with explicitly artificial test fixtures; then report
`SOURCE_PROFILE_UNRESOLVED`. Do not release a Vth-only or toy-beta substitute for
the required quantitative VTG Vth+beta profile.

## 4. Coordinates, extraction and units

Keep VTH_CC unchanged. Define an APM MG method with a versioned ID. At the reference
condition use magnitude coordinates U=VGS (N) or VSG (P), J=|ID| and
D=|VDS|=0.05 V, T=300 K=26.85 degC, VBS=0. Save raw signed terminal data too.
For an interior maximum of terminal dJ/dU at U*:

    beta_MG = gm_max / D
    VTH_MG  = U* - J(U*)/gm_max - D/2

beta_MG has units A/V^2 and includes the selected geometry's drive factor. It is
not a universal physical mobility or BSIM beta0. VTH_MG is a threshold-magnitude
coordinate; positive shifts increase magnitude for N and P, with backend signs
resolved separately.

Reuse the convergent preflight extractor after review. Save grid, interpolation,
derivative method, peak diagnostics and refinement results. Reject missing or
nonfinite data, insufficient interior coverage, unsupported competing peaks and
nonconvergent observables. A moving peak with stable extracted observables is not
automatically a failure. Do not exceed the family's permitted electrical domain
to force an interior peak. Never substitute constant-current extraction silently.

Persist W/L in metres; normalize source A_VT to V*m and A_beta to m for fractional
beta. Preserve reported units (e.g. mV*um or percent*um) alongside converted data.
The source active/drawn area and APM drawn/effective area are not interchangeable;
record the transfer convention rather than replacing source WL with BSIM Leff.

## 5. Statistical model and domain

For an approved equal-geometry independent-pair coefficient convention, define
individual q=(delta VTH_MG, delta beta_MG/beta_MG0) with covariance:

    Sigma_device = 1/(2 W L) * [[A_VT(L)^2, rho*A_VT(L)*A_beta(L)],
                               [rho*A_VT(L)*A_beta(L), A_beta(L)^2]]

Use independent physical-device draws; never assign +delta/2 and -delta/2 to force
a zero pair mean. For unequal devices, pair covariance is the sum of their
individual covariances under the stated local-independence assumption. Validate
source-specific pair normalization, including 2*(x1-x2)/(x1+x2) where applicable.
Finite pair-average denominators make the simple small-variation law approximate;
re-extract the actual statistic and quantify the deviation.

An independent rho=0 Croon approximation may be adopted only as a named model
assumption justified for the selected source/domain, not a universal 45 nm law.
Do not infer a full covariance from marginal error bars. Never import raw mobility
correlations as extracted-beta correlations without a transformation.

The individual fractional beta perturbation is Gaussian in the initial model.
Do not clip or resample a nonpositive beta target. Using ln(MULU0) in the solver
keeps the raw multiplier positive; it does not change the desired distribution
into a lognormal one. Any alternate distribution requires a recorded source/model
decision, not a convenience fix for failed tails.

Minimum numerical and default-profile target domain: VTG N/P, W=1-4 um,
L=0.12-0.40 um, calibrated at 300 K and 50 mV. The nine preflight grid points are
mandatory qualification anchors, not proof of all interior points. Verify
intermediate W/L holdouts and runtime mapping residuals. Use auditable interpolation
within approved coefficient support; label geometry transfer explicitly. Do not
claim measured support across that rectangle. If its statistical coverage cannot
be justified, report a material scope blocker rather than silently shrinking it.

Coefficient L interpolation must be explicit and versioned (piecewise linear in
log L is an initial candidate, not a law). Do not extrapolate beyond source support
or silently hold the last value constant. Fixed-L fourfold W should halve sigma;
changing L also changes A(L), so fourfold area alone does not imply halving.

300 K is the statistical anchor. Replaying identical raw devices at -40/27/85/125
degC is a predicted temperature response, not calibrated temperature-dependent
statistics. Do not claim calibrated weak-inversion/SS or cryogenic behavior.

## 6. Two-observable mapping

Map the desired q to raw x=(delta DELVTO, ln MULU0) with N/P-specific calibration
on the unmodified nominal model at the reference condition. Measure the full
Jacobian including cross terms; scale rows and columns before computing its
condition number. Use finite physical increments, a half-increment check and
bounded inversion. Do not let numerical derivatives approach machine precision.

Build a compact reusable map/surrogate if useful, but qualify unseen targets and
verify actual re-extracted q. Do not run a costly global optimization per device
where a qualified local inverse suffices. Cache by model/profile/extraction/mapping
identities and exact geometry, not a filename or nearest grid point alone.

After resolution, raw parameters are immutable for that realization across
bias/temperature/analysis changes. No per-operating-point refitting to preserve
q or Id. Re-resolving at a new W/L creates a new realization even when sharing z.

Before confirmation, freeze a numeric plan including grids, bounds, tolerances,
seeds and cohort sizes. Starting engineering budgets are: scaled condition number
<=100; half-step Jacobian relative change <=2%; extraction-refinement error <=0.5%
of each configured sigma; mapping holdout error <=2% of each sigma. Handle zero
sigma with declared absolute floors and zero-effect tests, never division by zero.
These are engineering acceptance budgets, not source measurement accuracies.
A justified budget revision requires a new recorded development plan before a new
confirmation cohort, not editing a failing report or silently relaxing a gate.

## 7. Tails and realizations

The preflight +/-10 mV and +/-2% targets do not establish +/-6 sigma support.
Once coefficients are approved, qualify a joint domain in latent coordinates
including simultaneous excursions and inversion positivity. Estimate campaign-wide
out-of-domain probability from the actual geometry/profile and scalar draw count.
For an independent standard-normal rectangular domain, a union-bound estimate is
2*N_scalar*Phi(-zmax); state assumptions and distinguish it from yield.

Target a predeclared default campaign of 100 two-coordinate MOS x 1024 samples
with estimated domain-exhaustion risk <=1e-3. Six-sigma marginal bounds are a
starting engineering choice, not proof that every raw corner is feasible. If the
model cannot support this without altering the distribution, publish the limitation
and block the minimum capability rather than clip or redraw. Record every requested,
executed, valid, failed and out-of-scope sample. A conditional successful-subset
statistic must be labeled and cannot silently stand for the whole population.

Separate latent_draw_id, device_realization_id and run_id. Key per-channel RNG by
root seed, sample index, stable physical device UID and random channel; exclude
worker ID, ordering, bias and temperature. Use stable cryptographic key encoding,
not Python hash(). Persist actual z values and raw resolved parameters; they are
the replay authority when RNG libraries change. Changing geometry/profile while
reusing z is common-random-number comparison, not the same physical realization.

Reject UID collisions and duplicate leaf assignments. Do not introduce physical
cross-family correlation by sharing a UID accidentally. Unit banks use independent
UIDs per physical unit. `m=N` or identical local draws are not equivalent to N
independent mismatch samples; public wrappers remain W/L-only.

## 8. Hierarchical application and run lifecycle

Accept an explicit instance map with stable UIDs, family selectors, exact geometry
and validated hierarchy segments. Resolve known public wrappers to internal leaves
without writing a speculative general netlist parser. Bind the circuit and all
resolved includes, models, instance map and analysis recipe by hashes.

Use instance alter, not shared-model altermod. Verify leaf existence, model/family,
W/L and raw DELVTO/MULU0 before and after application. Reject duplicate targets,
wrong family, absent paths, wrong geometry and unexpected parameter drift.
Never rely on return code alone: missing-leaf errors may return zero. Preserve
raw diagnostics and explicit expected-negative-control mechanisms.

Default: fresh ngspice -n -b process per uncached sample/condition with explicit
num_threads=1, known solver, captured startup environment and system-spinit
identity. -n does not imply all system initialization was ignored. Re-read applied
values before every analysis or fail if reset/reload invalidated them. DC/AC/tran
must use the same realization. No stale-state or cross-sample cache inheritance.
Provide unique output directories, deterministic parallel scheduling, timeout and
partial-log retention, and same-sample retries only. Do not retry with a new seed.

An authored analysis recipe is explicit trusted input, not an arbitrary generated
string interpolated from UIDs. Reject unsafe path/identifier syntax. Results and
errors are per experiment, polarity, sample and stage; one failure must not erase
independent findings. Bind caches to input and observed tool identities; tampered,
incomplete or mismatched cached results cannot pass.

## 9. Public API, reports and evidence tiers

Add a small research-variation command group with describe, sample, run and check
semantics; keep existing Benchmark commands unchanged. A user must be able to take
an included hierarchical mirror example, sample, run and replay it without importing
private Python functions. CLI spelling may be finalized once and documented.

Version new research request/profile/realization/run/report schemas separately.
Preserve existing released electrical/noise/benchmark schemas. Report variation
origin=research, included/excluded effects, source profile and extraction IDs,
source adoption/transfer tier, W/L support tier, temperature/bias support,
execution status and failures. Unknown or unavailable is not zero.

Profiles that supply only Vth require explicit user acknowledgement of excluded
beta and other effects; they are not total mismatch or full process MC. A complete
vtg quantitative release cannot be replaced by an artificial or partial profile.
No benchmark/native/research double-counting on the same leaf; reject overlapping
assignments rather than multiplying them silently.

Separate (a) software validation, (b) reproduction of configured APM statistics,
(c) agreement with selected source-derived observations, and (d) transfer hypotheses.
Display numerical PASS without converting it into foundry, yield or reliability
qualification. A source's confidence interval remains model uncertainty, not
extra within-die randomness.

## 10. Qualification design

Freeze a machine-readable confirmation plan before observing its results. Public
seeds are predeclared, not secretly sealed. Keep development and confirmation
cohorts distinct and record reuse; do not change seeds until tests pass.

A. Pure sampler: at least 65,536 pairs on artificial known coefficients; normal
marginals, means, covariance, independent instances, unequal geometry, sqrt(2),
fixed-L W scaling and A(L) interpolation. Test reorder/add-device/worker invariance.

B. Deterministic mapping: zero, axes, joint corners and independent holdouts through
the declared tail domain. Fine-grid re-extraction and untouched twins. Include bad
path, reset, wrong model/geometry, duplicate UID/leaf and corrupted cache/sample.

C. Real-SPICE statistics: at least 1,024 independent pairs at each mandatory nine
W/L anchor per polarity plus a declared intermediate-geometry set. Recover Vth and
beta distributions using the adopted normalization. Separate mapping bias from
sampling error. Plan simultaneous confidence/equivalence tests and multiplicity.
Starting sigma equivalence band: +/-10% for real-SPICE, +/-2% for pure sampling.
A wide confidence interval merely containing the target is insufficient. Chi-square
sigma intervals apply only where the normal assumption is appropriate; use a
predeclared bootstrap/nonlinear method for ratios otherwise. Reproducible tests
must not silently drop failed samples or depend on a lucky seed.

D. Cross-bias checks: at reachable nominal gm/Id=5/10/15 per VDS=0.05/0.5 V,
hold nominal gate bias fixed across samples. Compare measured current variance
with the actual simulator sensitivity prediction s^T Sigma s and separately with
simplified Croon. Report Croon approximation breakdown; do not tune A coefficients
to force it. Quantitative current-mismatch support requires a demonstrated valid
region, including at least two inversion levels for each polarity. Do not adjust
each sample's current or gm/Id before measuring common-bias variation.

E. Circuits: hierarchical N/P 1:1 and 1:4 mirrors, N/P input differential-pair
offset with explicitly ideal/excluded tail elements, and independent unit banks
N=1/4/16. At least 1024 realizations per confirmation circuit family. Match nominal
bias/voltage domain; keep systematic VDS error separate. Offset-balancing search
is a measurement, unlike retuning each transistor to erase current mismatch.
Validate first-order diagnostic relations only within their justified small-signal
range. Bank average scaling is a statistical property, not identical-sample equality.

F. Same realization: replay saved representative devices at -40/27/85/125 degC and
in DC/AC/transient; prove raw identity and readback stability. These temperature
responses are uncalibrated predictions. Minimal waveform/AC outputs and model
charge consistency are required; no PSS/noise-MC extension is included.

## 11. io18/io25 Vth-transfer assessment

Attempt a terminal-capacitance-based transfer assessment only after the core path
works. A long-L fit of Cgg/W versus L may estimate a capacitance-density slope and
an overlap intercept; call its epsilon/C result Tcap_proxy, not physical TOXE or
measured TINV. Check length-fit residuals, bias/frequency and model sensitivity.
A stable proxy does not validate a Takeuchi transfer across unrelated processes.

Use the actual adopted threshold extraction/work-function convention when assessing
Takeuchi-style normalization. Do not equate a hardcoded |Vth|+0.1 expression with
source electrostatics without a documented approximation. Never tune nominal io
cards or reuse the v4 construction ensemble as process variation.

Required report outcome per N/P and io family: SUPPORTED_HYPOTHESIS or
UNRESOLVED_WITH_EVIDENCE. An unexecuted investigation is not an allowed completed
outcome. Any public numeric scenario must be opt-in, explicitly Vth-only, carry
transfer uncertainty and excluded-beta warnings, and pass its own mapping tests.
If unresolved, provide no default numeric profile. This assessment does not expand
the mandatory complete-statistics scope beyond VTG.

## 12. Observed compiler provenance repair

Preflight observed a source different from the repository's expected OpenVAF pin.
Inspect the actual host again; do not assume it is unchanged. Fix live toolchain,
doctor, model-build metadata and cache logic so expected configuration cannot be
reported as observed provenance. The desired pin remains
`fdf2522b70f42793f64b1c72f0195c96dea0cc19` unless a separately reviewed goal changes it.

Record expected revision, observed source revision and cleanliness/submodules,
actual compiler path/version/binary SHA-256, build receipt, relevant Rust/LLVM/build
flags and OSDI output hashes. A nearby git checkout or version string alone does
not prove how a binary was built. Use a controlled pinned-source build with a
receipt binding source state and executable, or an equally verifiable existing
receipt. Unknown/mismatch must not pass the strict release-toolchain gate.

Build the pinned compiler in a project-local ignored prefix as necessary; do not
replace a user's system compiler, silently change the pin or erase old logs.
Invalidate stale caches whose identity was only asserted. Record native-BSIM4
runs as not using OpenVAF, independently of the complete-catalog gate.

New build metadata may use a versioned/additive format with explicit legacy-cache
handling. Preserve nominal electrical/noise result semantics and frozen historical
reports. Do not rewrite past PASS labels or claim earlier binaries' provenance has
been retrospectively established. Add tests for wrong pin, absent/unbound receipt,
changed binary, changed source/config and tampered cached OSDI metadata.

## 13. Implementation sequence and permissible changes

First bootstrap the active v5 mission/version/current validator together. The
handoff itself leaves 4.0.0+main software untouched; it does not claim old
maintenance string checks pass after instruction changes. Replace obsolete mission
assertions with explicit v5 lifecycle tests, retaining all legacy identity and
frozen-artifact checks. Do not weaken physics/provenance checks to unblock bootstrap.

Then work through compiler provenance and source audit in parallel with the core
runtime. Promote preflight algorithms into normal runtime modules; keep historical
preflight artifacts exact at the baseline. Add new research files outside models/
so nominal provenance inventories need not be rewritten. Do not build a plugin
framework or large registry service. Keep compiler and source dependencies visible
without stopping independent artificial implementation at the first unresolved item.

Before confirmation, commit approved sources, method IDs, parameters, plan, tests
and code. Record exact inspected/downloaded sources and source decisions. Develop
new evidence separately from immutable preflight and v4 records. Pin analysis and
simulator inputs; use compact manifest/report artifacts, not massive committed raws.

Mutable current files may change: AGENTS/GOAL/STATUS/live README/environment guidance,
current validators, src modules, tests, version metadata and local setup/provenance
support. Do not modify frozen v4 generator/release-validator trees, model bytes,
Benchmark v2 configs/semantics, native semantics or published tags/releases.

## 14. Release-readiness and lifecycle

Use 5.0.0.dev0 during implementation. Once all required methods/profiles/code/plans
are frozen, set plain 5.0.0 and create a clean candidate commit. Validate that exact
commit from a fresh clone using observed pinned tools; reports must not derive
identity merely from a pre-commit HEAD or editable-install version string.

Implement v5 candidate validation independently from historical v3/v4 release
workflows. Missing required fields, empty result lists, missing reports, stale hashes,
unknown tools and non-PASS mandatory gates fail closed. Optional/assessment outcomes
are predetermined in the gate contract. Do not reinterpret unresolved beta as a pass.

All candidate gates -> V5_RELEASE_READY -> human candidate approval -> immutable
annotated v5.0.0 -> fresh exact-tag requalification -> GitHub Release publication.
This task authorizes work through RELEASE_READY only. Do not create/publish a tag
or release without the separate approval. Post-tag validation is not a prerequisite
of pre-tag validation. Failed exact-tag validation never permits moving the tag.

After publication, a later maintenance update may use 5.0.0+main and mark v5 records
historical, without making current docs contradict active runtime checks. No minor
release milestones are introduced. Candidate/final reports live outside the tested
source identity; adding a later result-only summary does not certify its new commit.

## 15. Stop states and useful independent work

Material blockers: SOURCE_PROFILE_UNRESOLVED; SOURCE_GEOMETRY_AMBIGUOUS;
EXTRACTION_TRANSFER_UNRESOLVED; REQUIRED_DOMAIN_UNSUPPORTED;
MAPPING_ILL_CONDITIONED; TAIL_DOMAIN_INSUFFICIENT;
TOOLCHAIN_PROVENANCE_UNVERIFIED; LEGACY_REGRESSION_FAILED;
CONTRACT_CONTRADICTION; PUBLICATION_REQUIRES_APPROVAL.

Record per-stage evidence and continue independent authorized tasks. Do not invent
values, contact authors, silently narrow the minimum domain, clip/redraw samples or
publish a reduced v5 to force completion. Conversely do not repeatedly rerun an
already-qualified minimum preflight instead of implementing the usable flow.

## References and source boundaries

- Hart et al., original: https://doi.org/10.1109/JEDS.2020.2976546
- Hart et al., companion: https://doi.org/10.1109/JEDS.2020.2988730
- Hart thesis: https://doi.org/10.4233/uuid:0ab4ca6c-dc69-4207-970f-d3b9f0d9c5b4
- Companion full text: https://infoscience.epfl.ch/server/api/core/bitstreams/9cb2e29b-35ca-4052-ba6b-93ccbbde82e9/content
- Extraction review: https://doi.org/10.1016/S0026-2714(02)00027-6

The pinned preflight source audit supplies exact downloaded hashes and findings;
this contract adds no approved numeric beta coefficient. Repository implementation
facts come from the baseline source and preflight records, not from the articles.
