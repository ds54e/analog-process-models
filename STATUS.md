# APM v1.0 Implementation Status

This file is the compact persistent progress index for unattended execution.

It is **not** evidence by itself. Validation claims must point to committed summaries under `validation/evidence/` or to reproducible commands/tests.

## Overall state

- Project: Analog Process Models (APM)
- Repository: https://github.com/ds54e/analog-process-models
- Target: v1.0.0
- Current state: `IN_PROGRESS`
- Current milestone: `M4 Benchmark R/C + variation`
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
| M4 Benchmark R/C + variation | IN_PROGRESS | Implement common deterministic benchmark R/C and observable-intent MOS variation after three model families are running. |
| M5 APM022 | NOT_STARTED | — |
| M6 APM350 | NOT_STARTED | — |
| M7 Common characterization completion | NOT_STARTED | — |
| M8 IHP-native variation | NOT_STARTED | — |
| M9 Spectre model-only compatibility | NOT_STARTED | — |
| M10 License/provenance + clean-clone release review | NOT_STARTED | — |

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
`runtime.psp103_osdi`, `runtime.bsimcmg_osdi`, and `finfet.integrity`.

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

Only record decisions that materially affect public API, model provenance/fidelity, characterization semantics, variation semantics, supported runtime, or release claims. Do not use this section as a verbose work diary.

When a material decision intentionally departs from `PROJECT_CONTEXT.md`, record the new evidence and rationale here so future continuation does not accidentally revert it.

## Evidence index

- `validation/evidence/m0-runtime.md` — reference host/toolchain and four real simulator runtime smokes.
- `validation/evidence/m1-apm130.md` — nominal APM130 public devices and complete terminal characterization at required temperatures.
- `validation/evidence/m2-apm045.md` — exact-source nominal APM045 public devices and complete native-BSIM4 terminal characterization.
- `validation/evidence/m3-apm016f.md` — independently authored generic FinFET cards, genuine BSIM-CMG execution, and complete discrete-NFIN terminal characterization.

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
