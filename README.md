# Analog Process Models

**Repository:** https://github.com/ds54e/analog-process-models

Analog Process Models (**APM**) is a new project defined by this repository: an open, self-contained collection of analog compact-model technology kits and a common characterization framework for cross-process studies.

Within this repository, **APM means Analog Process Models**. It is not an external product, Microsoft technology, application-performance-monitoring package, or pre-existing software framework.

The v1.0 target spans five implemented model kits:

- **APM350** — 0.35 µm-class planar CMOS, BSIM3-class
- **APM130** — 130 nm planar CMOS, IHP SG13G2 / PSP103
- **APM045** — 45 nm planar CMOS, FreePDK45 / BSIM4
- **APM022** — 22 nm-class planar CMOS, APM-authored BSIM4 parameter deck
- **APM016F** — 16 nm-class FinFET, APM-authored parameters with BSIM-CMG

## Scope

The validated reference flow targeted for v1.0 is:

- WSL2
- AlmaLinux 9 / RHEL-compatible EL9 Linux, x86_64
- ngspice 47 with OSDI support
- Python
- OpenVAF-ReLoaded where Verilog-A-to-OSDI compilation is required
- xschem as an optional interactive frontend

APM is **not a manufacturable PDK** and does not provide layout rules, PCells, DRC, LVS, PEX, foundry signoff, or silicon-correlation guarantees.

The common v1.0 characterization contract implements Id–Vg, Id–Vd, gm/Id,
gm/gds, length scaling, DIBL, raw terminal small-signal admittance and derived
capacitance, four-temperature sweeps, common benchmark corners, and benchmark
process/mismatch/all Monte Carlo variation.

Technology-neutral benchmark resistor and capacitor models are included in scope so circuits can be compared without inventing process-specific passive technology for every node.

The benchmark variation/passive framework is implemented and real-tool
validated across all five kits and the BSIM3, PSP103, BSIM4, and BSIM-CMG
families. It uses observable `vth_shift`/`drive_shift` intents, persisted NumPy
PCG64 samples, fixed common corners, and native simulator R/C primitives. See
[`docs/benchmark-variation.md`](docs/benchmark-variation.md) for the exact
statistical, matching, sign, replay, and native-versus-benchmark semantics.

APM130 separately validates IHP's native `mos_tt/mos_ss/mos_ff/mos_sf/mos_fs`
corners, `mos_tt_stat` process profile, and `mos_tt_mismatch` local profile.
Those results retain exact upstream identities and are never translated into
benchmark labels. See [`docs/native-variation.md`](docs/native-variation.md).

## Backend status

| Backend / frontend | v1.0 status target |
| --- | --- |
| ngspice 47 + OSDI | **Validated reference backend** |
| xschem | Optional, example-supported frontend |
| Spectre | **Experimental / unverified**, model-only compatibility |
| Virtuoso | User-managed; no APM integration layer |

Spectre compatibility includes model files, benchmark corners, and benchmark Monte Carlo statistics, but is not considered validated until tested in a real Spectre environment.

Virtuoso libraries, symbols, CDFs, SKILL, ADE/Maestro setup, and other Virtuoso integration are user-managed and out of scope.

## Development and validation specification

The repository is designed so a long-running implementation agent can work without relying on conversational history or continuous human supervision.

- [`GOAL.md`](GOAL.md) — authoritative v1.0 implementation requirements and Definition of Done.
- [`AGENTS.md`](AGENTS.md) — mandatory repository-wide engineering and safety/quality constraints.
- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — condensed design history and rationale behind the v1.0 contract; informative, not normative.
- [`ENVIRONMENT.md`](ENVIRONMENT.md) — known starting WSL2/AlmaLinux state and M0 bootstrap expectations; reported state must be locally verified.
- [`RESEARCH_BASELINE.md`](RESEARCH_BASELINE.md) — dated upstream research facts used to seed implementation; re-check before pinning or release claims.
- [`RESULT_CONTRACT.md`](RESULT_CONTRACT.md) — stable v1 result semantics for units, geometry, raw/canonical quantities, Y-matrix data, derived metrics, and variation identity.
- [`UNATTENDED_EXECUTION.md`](UNATTENDED_EXECUTION.md) — required procedure for long-running autonomous implementation, checkpointing, blockers, and final clean-clone validation.
- [`STATUS.md`](STATUS.md) — compact persistent progress index; never evidence by itself.
- [`validation/release_gates.toml`](validation/release_gates.toml) — machine-readable v1.0 release-gate contract.
- [`validation/evidence/`](validation/evidence/) — compact committed audit evidence for completed validation claims.
- Per-kit `provenance.toml` files — model source/origin and licensing metadata.

For a deterministic benchmark sample and the current real-ngspice benchmark
regression:

```console
apm sample-variation --request examples/benchmark_request.json --mode all \
  --seed 20260830 --output results/all.json
apm benchmark-check --output results/benchmark-check
```

For complete nominal characterization and normalized comparisons:

```console
apm characterize apm045 --output results/apm045
apm characterization-check --output results/all-kits
apm compare apm022 apm016f --output results/apm022-vs-apm016f
apm apm130-native-check --output results/apm130-native
```

The repository remains under active v1.0 implementation. M0 through M8 are
validated; experimental Spectre model files, final release validation, and
clean-clone gates remain open. Do not interpret an implemented model as a
foundry or silicon-correlation claim. `STATUS.md` and committed evidence
identify the exact current boundary.
