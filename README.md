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

## Installation

The release reference is a clone on the WSL2 Linux filesystem (not `/mnt/c`)
running AlmaLinux 9 or another RHEL-compatible EL9 distribution on x86_64. On a
minimal AlmaLinux 9 installation, install the host build prerequisites:

```console
sudo dnf install -y \
  autoconf automake bison cpio curl flex gcc gcc-c++ git make \
  python3 python3-pip rpm tar
```

Clone the authoritative repository and build the pinned project-local
toolchain. The bootstrap downloads hash-pinned ngspice 47, AlmaLinux LLVM 20
RPMs, Rust 1.98.0, and the pinned OpenVAF-ReLoaded source; builds stay under the
ignored `.apm/` directory and do not edit shell startup files or
`~/.spiceinit`.

```console
git clone https://github.com/ds54e/analog-process-models.git
cd analog-process-models
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm build-models
.venv/bin/apm doctor
.venv/bin/apm validate
```

`apm validate` runs the full Python regression suite, Ruff, REUSE/SPDX,
provenance/distribution/claim audits, and the structural Spectre check. The
real-tool release flow is deliberately heavier and must start with an
attestation made immediately after a fresh clone, before bootstrap creates
`.apm/`:

```console
python3 tools/attest_clean_clone.py
tools/bootstrap-el9.sh
tools/setup-python.sh
.venv/bin/apm validate --release
```

That single release command rebuilds/loads the required OSDI models, runs the
headless doctor, benchmark and APM130-native variation checks, and performs a
fresh all-five-kit characterization and normalized comparison. It exits
nonzero for a failed, skipped, unimplemented, or evidence-free required gate.
See [`docs/release-validation.md`](docs/release-validation.md) for the exact
clean-clone protocol and report layout. The attestation is a release-audit step;
ordinary development on another supported Python host can omit it, but such a
host does not satisfy the v1.0 reference-environment gate.

## Model provenance

The repository ships every transistor-model source needed after cloning; only
generated OSDI binaries are built locally. Each kit has a machine-readable
`provenance.toml` with source identity, exact revision, redistribution basis,
file SHA-256 values, modifications, validation boundary, and Spectre status:

- [`models/apm350/provenance.toml`](models/apm350/provenance.toml) —
  APM-authored Apache-2.0 generic BSIM3 deck; the ambiguously sourced candidate
  card was rejected and is not shipped or used numerically.
- [`models/apm130/provenance.toml`](models/apm130/provenance.toml) — pinned IHP
  SG13G2 Apache-2.0 cards and PSP/JUNCAP source under the preserved Si2 terms.
- [`models/apm045/provenance.toml`](models/apm045/provenance.toml) —
  byte-identical nominal VTG subset from the Apache-2.0 open-source-clean
  FreePDK45 mirror.
- [`models/apm022/provenance.toml`](models/apm022/provenance.toml) —
  APM-authored Apache-2.0 BSIM4 parameters, explicitly not PTM-derived.
- [`models/apm016f/provenance.toml`](models/apm016f/provenance.toml) —
  APM-authored Apache-2.0 parameters with byte-identical ECL-2.0 UC Berkeley
  BSIM-CMG 112.1.0 engine sources and notices.

[`THIRD_PARTY.md`](THIRD_PARTY.md) explains the licensing decisions, and
`REUSE.toml` plus `LICENSES/` provide the repository-wide SPDX/REUSE mapping.
The release audit requires the vendored filesystem to match the imported-file
manifests exactly and rejects a changed or unaccounted file.

## Model fidelity and limitations

APM350, APM022, and the APM016F parameter deck are open generic behavioral
references, not measured foundry models. APM130 derives from the open IHP model
set and APM045 from the predictive FreePDK45 model set, but APM makes no silicon
correlation, yield, signoff, or fitness claim for either. APM045 retains its
disclosed upstream PTM ancestry; its values were not used to author APM022.
Official PTM/PTM-MG cards are neither shipped nor numeric inputs to APM022 or
APM016F.

The supported public geometry and bias ranges are those in each `kit.toml`.
Model behavior outside those characterized ranges is unqualified. V1 excludes
MOS noise characterization, RF devices, native passives as a common basis,
layout, PCells, DRC/LVS/PEX, standard cells, AMS, and foundry signoff. The
benchmark distributions are synthetic comparison knobs rather than silicon
statistics. Spectre limitations are stricter and are stated separately below.

## Comparison methodology

`apm characterization-check --output DIR` regenerates and audits every kit,
then compares N/P devices at 27 °C, `L/Lmin=2`, `VOUT/VDD=0.5`, and the sampled
point nearest `gm/Id=15 1/V`. Raw simulator-signed terminal quantities remain
available, while canonical N/P comparison quantities use positive effective
control/output voltages and `IDMAG` so PFET results are not sign-inverted.

Planar current, gm, and capacitance are reported per micrometre of drawn width;
FinFET quantities are reported per fin. APM does not invent a width-to-fin
conversion or report ratios across those different bases. Raw complex terminal
Y data remains authoritative for derived capacitance. The complete terminal,
normalization, finite-difference, and Y-matrix conventions are in
[`RESULT_CONTRACT.md`](RESULT_CONTRACT.md) and
[`docs/characterization.md`](docs/characterization.md).

The common passives are `Rbench` and `Cbench`; both expose a positive,
dimensionless `match_size` whose local sigma scales as
`1/sqrt(match_size)`. Their temperature, value-resolution, and resistor-noise
semantics are documented with benchmark-versus-native variation boundaries in
[`docs/benchmark-variation.md`](docs/benchmark-variation.md).

## Backend status

| Backend / frontend | v1.0 status target |
| --- | --- |
| ngspice 47 + OSDI | **Validated reference backend** |
| xschem | Optional, example-supported frontend |
| Spectre | **Experimental / unverified**, model-only compatibility |
| Virtuoso | User-managed; no APM integration layer |

Spectre compatibility includes model files for all five kits, benchmark R/C,
five benchmark corners, and `statistics` blocks for Process, Mismatch, and All.
It has passed the required static structural gate only and is not considered
validated until tested in a real Spectre environment. See
[`docs/spectre.md`](docs/spectre.md) for exact inclusion, distribution,
geometry, correlation, translation, and claim boundaries.

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
- [`docs/release-validation.md`](docs/release-validation.md) — fail-closed validator, clean-clone attestation, and release evidence procedure.
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
apm spectre-check --output results/spectre-structural
```

Every v1.0 release claim is tied to a required entry in
[`validation/release_gates.toml`](validation/release_gates.toml). M0 through M8
have real-tool evidence; the M9 model-only Spectre gate is structural only and
the backend remains explicitly experimental/unverified. Do not interpret an
implemented model as a foundry or silicon-correlation claim. `STATUS.md`, the
committed evidence summaries, and the machine-readable release report identify
the exact validated boundary.
