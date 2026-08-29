# APM v1.0 Implementation Status

This file is the compact persistent progress index for unattended execution.

It is **not** evidence by itself. Validation claims must point to committed summaries under `validation/evidence/` or to reproducible commands/tests.

## Overall state

- Project: Analog Process Models (APM)
- Repository: https://github.com/ds54e/analog-process-models
- Target: v1.0.0
- Current state: `IN_PROGRESS`
- Current milestone: `M10 License/provenance + clean-clone release review`
- Release eligible: `NO`

## Reported initial environment

The following was the user-reported starting context before M0:

- Codex CLI is running directly inside WSL2 on AlmaLinux.
- ngspice is not currently installed.
- OpenVAF-ReLoaded is not currently assumed to be installed.
- PSP103 / BSIM-CMG OSDI build artifacts are not currently assumed to exist.

See `ENVIRONMENT.md`. M0 verified the host and bootstrapped the project-local reference toolchain without root access.

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| M0 Runtime qualification | VALIDATED | `validation/evidence/m0-runtime.md`: reproducible project-local bootstrap and real native BSIM3/BSIM4, PSP103 OSDI, and BSIM-CMG OSDI simulations passed. |
| M1 APM130 | VALIDATED | `validation/evidence/m1-apm130.md`: public N/P wrappers and complete nominal terminal characterization passed at all temperatures and lengths, including PSP native gm/gds oracle agreement. |
| M2 APM045 | VALIDATED | `validation/evidence/m2-apm045.md`: exact Apache-2.0 FreePDK45 VTG subset, public N/P wrappers, and complete native-BSIM4 terminal characterization passed. |
| M3 APM016F | VALIDATED | `validation/evidence/m3-apm016f.md`: independent APM cards, genuine BSIM-CMG OSDI, discrete `l,nfin` public results, and complete nominal terminal/NFIN characterization passed. |
| M4 Benchmark R/C + variation | VALIDATED | `validation/evidence/m4-benchmark.md`: frozen synthetic severities, measured PSP/BSIM4/BSIM-CMG intent adapters, deterministic PCG64 samples/replay, five common corners, and native R/C value/noise checks passed. |
| M5 APM022 | VALIDATED | `validation/evidence/m5-apm022.md`: independent non-PTM BSIM4 cards, explicit behavior contracts, complete terminal characterization, APM045/APM016F comparisons, and benchmark adapter/corners passed. |
| M6 APM350 | VALIDATED | `validation/evidence/m6-apm350.md`: independently authored open generic BSIM3 cards, rejected-source license audit, complete terminal characterization, and fifth benchmark adapter passed. |
| M7 Common characterization completion | VALIDATED | `validation/evidence/m7-all-kits.md`: fresh all-kit execution, complete result-contract audits, normalized terminal comparison, and explicit planar-per-width versus FinFET-per-fin semantics passed. |
| M8 IHP-native variation | VALIDATED | `validation/evidence/m8-apm130-native.md`: all five IHP corners plus 128-sample native process/mismatch cohorts, replay, global/local semantics, and geometry scaling passed in ngspice. |
| M9 Spectre model-only compatibility | VALIDATED | `validation/evidence/m9-spectre.md`: all five kits, benchmark R/C, five corners, Process/Mismatch/All statistics, provenance, and model-only scope passed the required static gate; backend remains experimental/unverified with no Spectre parse claim. |
| M10 License/provenance + clean-clone release review | IN_PROGRESS | Implement the release validator, finish metadata/claim/licensing audits, then execute the full fresh-clone release protocol. |

Allowed milestone status values:

- `NOT_STARTED`
- `IN_PROGRESS`
- `VALIDATED`
- `BLOCKED`

Do not mark a milestone `VALIDATED` when its required real-tool checks have not run successfully.

## Validated reference environment

Reference environment and simulator runtime qualified on 2026-08-29 UTC:

Record actual validated values when M0 runs:

- WSL version / host context: WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`
- EL9 distribution and version: AlmaLinux 9.7
- architecture: x86_64
- repository path/filesystem: `/home/admin/src/analog-process-models` on Linux ext4 (`/dev/sdd`), not `/mnt/c`
- Python version: 3.9.25
- ngspice version/build options/prefix: ngspice 47; `--enable-predictor --enable-osdi --with-x=no`; project-local `.apm/toolchain/ngspice-47`
- OSDI load mechanism: ngspice `pre_osdi` inside a headless `.control` block
- OpenVAF-ReLoaded version/revision: tag `v24.0.2mob`, commit `fdf2522b70f42793f64b1c72f0195c96dea0cc19`, source-built against AlmaLinux LLVM 20.1.8
- PSP103 source/revision: PSP 103.8.2 / JUNCAP 200.6.2 from IHP commit `331c00484213b13414777eec1336ef5c29b969bd`; IHP parameter cards identify PSP 103.6
- BSIM-CMG source/revision: UC Berkeley BSIM-CMG 112.1.0, upstream archive SHA-256 `9c70a7c9fcfafe66fb1582655bbfd36714b90ecba137a9dd83c76b3a0bd9e50a`

## Release-gate summary

The normative gate definition is `validation/release_gates.toml`.

Validated gates: `runtime.wsl2_el9`, `runtime.ngspice_headless`,
`runtime.psp103_osdi`, `runtime.bsimcmg_osdi`, `models.all_kits`,
`characterization.all_kits`, `passives.benchmark`, `variation.benchmark`,
`variation.apm130_native`, `finfet.integrity`, and `spectre.model_only`.

All remaining gates are unvalidated.

Do not convert absence of evidence into PASS.

## Current blockers

None recorded yet. Missing initial simulator/compiler installations are expected M0 bootstrap work, not blockers by themselves.

A blocker entry should state:

- affected milestone/gate;
- exact blocker;
- investigation performed;
- compliant alternatives considered;
- whether independent work can continue.

## Material decisions made during implementation

- The official OpenVAF `v24.0.2mob` Linux binary requires glibc newer than EL9 and an unavailable `libLLVM.so.18.1`. The reproducible bootstrap therefore builds the pinned `openvaf-driver` source package against project-local AlmaLinux LLVM 20.1.8. This preserves the EL9 reference platform.
- Current IHP upstream combines PSP 103.6 parameter cards with PSP 103.8.2 source. APM pins both exact assets, records the distinction, and has verified their nominal QS combination in real ngspice 47. No card values were translated or changed.
- APM130 uses the upstream-documented 1.2 V thin-oxide supply and 0.13 um model Lmin. Its canonical threshold method is `Id=100 nA * W/L`; the coefficient, geometry, and drain biases are persisted with every DIBL result.
- APM045 pins the open-source-clean FreePDK45 1.4 mirror at commit `688ee68ec5301e5fe11ebee5e53c1109d3cfd51d` and ships only its byte-identical nominal VTG cards plus licensing/model-basis documents. Its disclosed PTM ancestry is isolated from the independently authored APM022 deck.
- APM045 uses 101-point DC sweeps so the 1.0 V endpoints and 10 mV finite-difference grid are exact. Monotonicity is required from the documented constant-current criterion through conduction; full-range picoamp leakage-partition reversals are retained and reported separately.
- APM016F uses the exact ECL-2.0 Berkeley BSIM-CMG 112.1.0 engine with independently authored Apache-2.0 parameter cards. Public dimensions, doping, 0.8 V operation, and behavior targets come from cited primary literature and official BSIM-CMG semantics; no PTM-MG card values were used. Its public/result geometry is only `l,nfin`, threshold extraction is `Id=100 nA*NFIN`, self-heating is off, and a 5 mV gate grid provides converged canonical gm.
- APM022 is an independently authored native-BSIM4 22 nm-class deck using
  public quasi-planar bulk dimensions and official BSIM semantics, with no PTM
  card use. Its supported v1 range is L=25..100 nm at 0.8 V. The card
  explicitly disables the unevidenced BSIM pocket-length default, and terminal
  gates enforce monotonic threshold/gain increase, monotonic DIBL decrease,
  minimum-length behavior ranges, and the required APM045/APM016F comparisons.
- APM350 does not vendor the preferred SCN4M_SUBM candidate card because its
  exact file has no original-source or file-level rights statement. It instead
  uses an independently authored Apache-2.0 BSIM3 generic reference, while the
  pinned MIT README supplies only class-level 0.4 um Lmin, 0.6 um Wmin, and 5 V
  statements. The technology label remains 0.35 um-class and the actual model
  minimum is recorded honestly as 0.4 um.
- APM benchmark variation uses frozen synthetic sigmas only after real PSP103,
  BSIM4, and BSIM-CMG calibration. Canonical positive threshold shift means
  larger `|Vth|` for N/P even though raw signs differ; canonical positive drive
  shift means larger reference-bias `|Id|`. NumPy PCG64 resolves deterministic
  samples outside ngspice, and persisted samples are the replay authority.
- Benchmark process variables are independent/global per class; mismatch is
  independent/local per instance; threshold combines additively while drive
  and passive scale factors combine multiplicatively. Planar matching uses
  `W*L`, FinFET matching uses `NFIN*L`, and passive `match_size` is dimensionless.
- Integrated comparisons use 27 degC, `L/Lmin=2`, `VOUT/VDD=0.5`, and the
  available gate-grid point nearest `gm/Id=15 1/V`. Planar current/gm/
  capacitance remain per micrometre of drawn width and FinFET quantities remain
  per fin; cross-basis current and capacitance ratios are intentionally absent.
- APM130's selected native flow retains the five upstream `mos_*` corners,
  `mos_tt_stat`, and `mos_tt_mismatch` identities and uses
  ngspice-native seeded random evaluation. It has no stochastic native `all`
  profile because upstream provides none. The sole 1e-9 relative PMOS
  `dphiblw` process entry is persisted but explicitly classified as effectively
  fixed at ngspice 47 expanded-deck precision; 33 process fields vary measurably.
- Spectre v1 artifacts are a model-only, static-checked layer with one common
  variation library: five deterministic benchmark sections and a `bench_mc`
  section whose normal Spectre `process`/`mismatch` blocks support user-selected
  Process, Mismatch, or All. Six process variables are independent/global;
  four mismatch variables are independent and referenced within regular
  device/passive subcircuits for per-instance sampling. Public sizing remains
  planar `w,l` or FinFET `l,nfin`; no testbench or Virtuoso asset is shipped.
- APM130's Spectre nominal card is a deterministic Apache-2.0 translation of
  the pinned IHP TT QS subset. It preserves the selected 34 global and two N/P
  model-block parameter values, changes only `psp103va` to native `psp103`, and
  fixes upstream wrapper-scope inputs. IHP-native Spectre MC, Spectre parsing,
  and numerical conformance remain explicitly unclaimed.

Only record decisions that materially affect public API, model provenance/fidelity, characterization semantics, variation semantics, supported runtime, or release claims. Do not use this section as a verbose work diary.

When a material decision intentionally departs from `PROJECT_CONTEXT.md`, record the new evidence and rationale here so future continuation does not accidentally revert it.

## Evidence index

- `validation/evidence/m0-runtime.md` — reference host/toolchain and four real simulator runtime smokes.
- `validation/evidence/m1-apm130.md` — nominal APM130 public devices and complete terminal characterization at required temperatures.
- `validation/evidence/m2-apm045.md` — exact-source nominal APM045 public devices and complete native-BSIM4 terminal characterization.
- `validation/evidence/m3-apm016f.md` — independently authored generic FinFET cards, genuine BSIM-CMG execution, and complete discrete-NFIN terminal characterization.
- `validation/evidence/m4-benchmark.md` — calibrated observable-intent mappings,
  deterministic benchmark modes/corners/replay, and technology-neutral R/C
  value, temperature, matching, and native-noise validation.
- `validation/evidence/m5-apm022.md` — independent scaled-planar cards,
  terminal behavior and cross-kit comparisons, plus the calibrated APM022
  benchmark adapter and deterministic variation rerun.
- `validation/evidence/m6-apm350.md` — rejected-candidate provenance audit,
  independent mature-planar BSIM3 characterization, and the completed
  five-kit benchmark adapter/corner/Monte Carlo validation.
- `validation/evidence/m7-all-kits.md` — fresh five-kit characterization,
  persisted result-contract audit, normalized terminal table, and safe
  planar-to-FinFET comparison semantics.
- `validation/evidence/m8-apm130-native.md` — five pinned IHP corner profiles,
  model-global native process sampling, instance-local native mismatch,
  deterministic replay, and upstream geometry scaling in real ngspice.
- `validation/evidence/m9-spectre.md` — structurally checked model-only files
  for all five kits, common corners/statistics/passives, exact adapter and
  provenance audits, and explicit experimental/unverified evidence boundary.

## Final-review fields

Complete these only during M10:

- clean clone path/environment:
- clean-clone setup result:
- `apm doctor` result:
- complete test-suite result:
- `apm validate --release` result:
- all-five-kit comparison result:
- provenance/license audit result:
- README claim audit result:
- release-critical placeholder/TBD scan result:
- package version (`pyproject.toml`) = 1.0.0:
- runtime `__version__` = 1.0.0:
- `CHANGELOG.md` v1.0.0 release entry present:
- Spectre status confirmed experimental/unverified:
- final release commit:
- v1.0.0 tag created: NO
