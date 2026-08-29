# Project Context and Design Rationale

This file captures the design context behind `GOAL.md` so an implementation agent can understand *why* the repository contract looks the way it does.

It is informative, not normative. If this file conflicts with `AGENTS.md` or `GOAL.md`, follow `AGENTS.md` and `GOAL.md` and record the discrepancy in `STATUS.md`.

## Project intent

Analog Process Models (APM) is a new project defined by this repository. The intent is to create a compact, self-contained, open collection of analog transistor model kits spanning several process generations, plus one reproducible characterization methodology that makes cross-generation analog studies practical.

The project deliberately targets simulation and characterization rather than manufacturability. It is not trying to become a complete foundry PDK, an educational layout kit, or a physical-design platform.

The important product is therefore not only a collection of model cards. It is the combination of:

- model assets with explicit provenance and fidelity limits;
- a reproducible ngspice reference flow;
- common terminal-level characterization semantics;
- common benchmark variation semantics;
- technology-neutral benchmark R/C models;
- enough metadata and evidence that comparisons remain interpretable.

## Why these five technology kits

The v1.0 sequence is intended to cover both process scaling and a device-architecture transition:

`0.35 um-class planar -> 130 nm planar -> 45 nm planar -> 22 nm-class planar -> 16 nm-class FinFET`

The current five-kit set is:

1. **APM350** — mature/long-channel planar anchor, BSIM3-class.
2. **APM130** — open foundry-derived anchor using IHP SG13G2 low-voltage MOS and PSP103.
3. **APM045** — generic scaled-planar anchor using an open FreePDK45 BSIM4 subset.
4. **APM022** — APM-authored aggressively scaled planar BSIM4 deck.
5. **APM016F** — APM-authored FinFET parameter deck using a pinned BSIM-CMG engine.

A 55 nm kit was considered earlier. It was removed from v1.0 because a clearly redistributable, sufficiently useful open 45 nm model already exists, while a credible 55 nm model would likely require additional synthetic-model development or reliance on less mature sources. The 45 nm choice reduces project risk while preserving the intended scaled-planar comparison point. A future 55 nm kit remains possible but is not part of v1.0.

## Provenance classes and fidelity claims

The kits intentionally have different origins. Do not flatten these distinctions.

- **APM350:** generic open reference model. It is a technology-class anchor, not a foundry-correlated claim.
- **APM130:** foundry-derived open model subset from IHP SG13G2. This is the strongest real/open anchor in the set, but APM still does not make independent silicon-correlation guarantees.
- **APM045:** open predictive/generic FreePDK45 model subset. Useful for scaled-planar studies, not a manufacturing guarantee.
- **APM022:** `apm_generic`, independently authored by APM.
- **APM016F:** `apm_generic`, independently authored APM parameters with an open/pinned BSIM-CMG engine.

The user-facing guarantee is reproducible simulation and comparison methodology, not process qualification or silicon accuracy.

## Why PTM/PTM-MG are not vendored or used as parameter sources

Official PTM/PTM-MG model cards are useful technical references, but their redistribution permission was not considered sufficiently clear for a repository whose goal is clone-and-use distribution. Therefore v1.0 must not bundle official PTM22 or PTM-MG16 parameter decks.

More importantly, APM022 and APM016F must not simply become renamed or interpolated PTM cards. Their parameter decks are intended to be independently authored from:

- public literature;
- BSIM4 / BSIM-CMG model semantics and documentation;
- published representative device characteristics;
- explicit APM behavior contracts.

PTM/PTM-MG may be used locally only as non-redistributed sanity/comparison oracles. They are not numeric source material for APM-authored parameter decks.

This distinction matters both for licensing clarity and for intellectual honesty in model provenance.

## Why ngspice is the validated reference backend

The project needs an open, reproducible, headless flow that can run in CI-like environments and on the user's primary development platform.

The chosen reference environment is:

- WSL2;
- RHEL-compatible EL9 Linux, x86_64;
- ngspice with OSDI support;
- Python;
- OpenVAF-ReLoaded when Verilog-A compact models need compilation;
- xschem only as an optional example/manual frontend.

The project should not depend on GUI state or user-global simulator configuration. Runs should be hermetic and should prefer netlist-local model loading such as `pre_osdi` where practical.

The intended execution path is roughly:

- APM350 -> native ngspice BSIM3;
- APM130 -> PSP103 Verilog-A compiled to OSDI;
- APM045 -> native ngspice BSIM4;
- APM022 -> native ngspice BSIM4;
- APM016F -> BSIM-CMG Verilog-A compiled to OSDI.

`apm doctor` is expected to exercise real model instances, not merely check file existence.

## Why compact-model APIs are not unified

A central design principle is:

> Commonize the characterization contract, not the compact-model API.

BSIM3, PSP103, BSIM4, and BSIM-CMG have different parameter vocabularies, geometry semantics, internal operating-point names, and model capabilities. Attempting to hide those differences behind a large universal MOS API would create an artificial abstraction and would likely distort FinFET semantics.

The common public interface is intentionally minimal:

- planar: D/G/S/B plus W/L;
- FinFET: D/G/S/B plus L/NFIN.

The common cross-technology layer exists at the measurement/result level: Id-Vg, Id-Vd, gm/Id, gm/gds, DIBL, terminal Y/capacitance, temperature, corners, and benchmark variation.

This is also why v1.0 does not expose common `m`, `nf`, `ng`, or finger semantics. Multiplicity and fingerization carry model/layout-specific matching and correlation assumptions that are outside the desired v1.0 scope.

## Why canonical gm/gds come from terminal finite differences

Model families and simulators expose internal operating-point fields differently. An internal field such as `gm` is useful as a validation oracle, but it is a poor stable API across PSP, BSIM, BSIM-CMG, ngspice, and future Spectre support.

Therefore canonical gm and gds are derived from terminal behavior with central finite differences and convergence checks. APM130 should compare these derived values with PSP-native operating-point quantities to validate the extraction method.

For N/P comparison, the canonical comparison metrics use positive effective variables and current magnitude while preserving raw signed simulator data separately. This prevents accidental PMOS sign inversions in gm/Id and gm/gds plots.

## Why capacitance comes from the terminal Y matrix

The same portability issue applies to compact-model-specific capacitance fields. The canonical source is the small-signal terminal admittance matrix.

The project stores the raw complex Y matrix and derives reported capacitances from it. Keeping raw Y data means capacitance definitions can be improved later without rerunning every simulation.

This is more durable than making model-specific `cgg`, `cgd`, or `cgs` names part of the public contract.

## Why there are two distinct variation systems

Two different questions are useful and must not be confused:

1. **PDK-native variation:** what the upstream model itself predicts.
2. **APM benchmark variation:** what happens when comparable synthetic variation severity is applied across technologies.

APM130/IHP can expose native corners and native statistical/mismatch behavior on the validated ngspice side. Those results are useful as native model behavior, but they are not directly comparable to a synthetic common variation model applied to every kit.

Every result therefore needs a clear distinction such as `variation_origin = native` versus `variation_origin = benchmark`.

## Why benchmark MOS variation has only `vth_shift` and `drive_shift`

The benchmark model intentionally avoids randomizing dozens of raw compact-model parameters.

The common intents are:

- `vth_shift` — observable threshold-behavior shift;
- `drive_shift` — observable relative Id shift at a documented reference bias.

Each kit maps these intents to model-family-specific handles. Candidate handles include `delvto`/`mulu0` for BSIM, `delvto`/`factuo` for PSP, and `DELVTRAND` plus `IDS0MULT` or `U0MULT` for BSIM-CMG. These mappings must be characterized, not assumed.

The important semantic is the observable effect. Equal raw percentages in two unrelated compact-model parameters are not automatically comparable.

`drive_shift` should therefore be calibrated against a documented reference operating point, approximately around moderate inversion such as `L ~= 2*Lmin`, `VDS ~= 0.5*VDD`, `gm/Id ~= 15 V^-1`, with the exact implementation justified by characterization.

## Why benchmark sigma values remain TBD initially

The architecture of benchmark variation is part of the v1.0 contract. The numerical severities are deliberately not preselected.

Choosing convenient sigma values before representative PSP, BSIM4, and BSIM-CMG devices are running would create false precision. The implementation agent should first make representative kits operational, measure the actual observable effects, then freeze documented benchmark values with evidence.

The same applies to benchmark R/C variation severity and deterministic benchmark-corner strength.

TBDs are therefore temporary development markers, not permission to leave release metadata incomplete. No release-critical TBD may remain at v1.0.0.

## Why ngspice benchmark Monte Carlo uses Python RNG

The reference benchmark MC flow is intentionally:

`Python RNG -> resolved VariationSample -> deterministic netlist -> ngspice`

Reasons include:

- seed reproducibility;
- explicit process/local semantics;
- deterministic replay;
- independence from compact-model random-number support;
- avoiding dependence on Verilog-A RNG capabilities in the OSDI toolchain;
- making samples inspectable and potentially reusable for later cross-simulator conformance.

A resolved sample should contain enough global/local MOS and R/C perturbation information to reproduce a run exactly.

Spectre does not need to reproduce Python RNG sample-for-sample in v1.0. Its native statistics machinery may generate samples, provided intended distributions, geometry scaling, process/local semantics, and documented correlation assumptions match the APM benchmark definition.

## Benchmark mismatch intent

The benchmark mismatch law is synthetic and technology-neutral by design. It is not a claim about real foundry Pelgrom coefficients.

The intended scaling is approximately:

- planar matching size proportional to W*L relative to a reference;
- FinFET matching size proportional to NFIN*L relative to a reference;
- local sigma proportional to `1/sqrt(match_size)`.

This gives circuit designers a common matching-aware design variable without pretending every open technology kit has comparable measured mismatch data.

## Why benchmark R/C exist separately from native passives

Cross-process circuit comparison can be distorted if one process has detailed native resistor/capacitor models and another requires invented approximations.

Therefore v1.0 includes technology-neutral `Rbench` and `Cbench` primitives with common process/mismatch semantics. These are the golden cross-process passive basis.

Native passives may be exposed where reliable open models exist, especially for IHP, but they are optional and must never silently become the cross-process golden comparison basis.

`match_size` for benchmark passives is a dimensionless benchmark quantity, not claimed physical layout area.

## Why Spectre support is model-only and experimental

Cadence compatibility is valuable to analog designers, so v1.0 should include a model compatibility layer rather than postponing all Spectre work.

However, the initial project does not have a locally validated Spectre/Virtuoso environment. Therefore Spectre support must remain explicitly:

`EXPERIMENTAL / UNVERIFIED`

The intended deliverable is model files only:

- nominal model interfaces;
- benchmark corners;
- benchmark R/C;
- benchmark Process/Mismatch/All Monte Carlo definitions.

Virtuoso symbols, CDF, OA libraries, SKILL, ADE/Maestro configuration, OCEAN, and testbenches are not APM v1.0 responsibilities.

The preferred Spectre design uses native compact-model implementations with thin APM-owned subcircuit wrappers, especially because per-instance mismatch semantics are easier to express cleanly through wrappers plus `statistics` blocks.

Do not claim Spectre parse validity or numerical conformance until a real Spectre environment has tested it.

## Why MOS noise is deferred

MOS noise is intentionally out of v1.0.

The simulator/model engines can support noise-related behavior, but credible cross-technology noise requires credible noise parameterization and careful validation. Including nominal-looking noise curves without trustworthy model inputs would create misleading confidence.

The v1.0 architecture should not block future noise characterization, but MOS noise itself belongs in a later release.

Normal SPICE resistor thermal noise need not be reimplemented; benchmark resistors should use ordinary simulator resistor primitives.

## Expected development order and rationale

The preferred order is not arbitrary:

1. **M0 runtime qualification** — prove all required model families can execute in the target environment.
2. **APM130** — use the strongest open/foundry-derived anchor to establish characterization methodology.
3. **APM045** — ensure the framework is not PSP-specific.
4. **APM016F** — introduce FinFET geometry early so planar assumptions do not harden into the architecture.
5. **Benchmark R/C + variation** — design common semantics after multiple model families are actually running.
6. **APM022** — author the aggressively scaled planar model with the working framework and FinFET comparison already available.
7. **APM350** — add the mature long-channel anchor.
8. Complete common characterization and native IHP variation.
9. Add experimental Spectre model-only compatibility.
10. Perform license/provenance, fresh-clone, and claim audits before v1.0.0.

Do not reorder merely for convenience if doing so encourages premature abstraction or arbitrary benchmark calibration. Reordering is acceptable when actual tool or source evidence provides a concrete reason.

## Important qualitative behavior contracts

APM022 should, over documented supported operating ranges, show behavior qualitatively consistent with an aggressively scaled planar generation relative to APM045, including stronger short-channel effects, larger DIBL near Lmin, and lower intrinsic gain near Lmin.

APM016F should genuinely exercise BSIM-CMG and FinFET sizing. Id and gm should scale sensibly with NFIN, while gm/Id should be broadly less sensitive to NFIN at a common bias condition. Electrostatic control should be qualitatively improved relative to APM022.

These are behavior contracts, not invitations to tune against a hidden PTM numeric deck.

## Release philosophy

The release should be conservative in claims and strict in evidence.

A file existing is not proof that a model works. A static Spectre file check is not Spectre validation. A container test is not the required WSL2+EL9 clean-clone validation. A repository-level license is not automatically enough to redistribute every vendored file.

The v1.0 release should prioritize:

- reproducibility;
- explicit provenance;
- explicit uncertainty;
- stable characterization semantics;
- honest backend validation status;
- a small architecture that can be extended later.

If a mandatory requirement remains genuinely blocked, complete all independent work and leave the repository auditable, but do not silently downgrade the requirement or tag an incomplete v1.0.0.
