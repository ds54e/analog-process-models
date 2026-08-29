# Analog Process Models

Analog Process Models (APM) is an open, self-contained collection of analog compact-model technology kits and a common characterization framework for cross-process studies.

The planned v1.0 spans:

- **APM350** — 0.35 µm-class planar CMOS, BSIM3-class
- **APM130** — 130 nm planar CMOS, IHP SG13G2 / PSP103
- **APM045** — 45 nm planar CMOS, FreePDK45 / BSIM4
- **APM022** — 22 nm-class planar CMOS, APM-authored BSIM4 parameter deck
- **APM016F** — 16 nm-class FinFET, APM-authored parameters with BSIM-CMG

## Scope

The validated reference flow for v1.0 is planned to be:

- WSL2
- RHEL-compatible EL9 Linux, x86_64
- ngspice with OSDI support
- Python
- xschem as an optional interactive frontend

APM is **not a manufacturable PDK** and does not provide layout rules, PCells, DRC, LVS, PEX, foundry signoff, or silicon-correlation guarantees.

The common v1.0 characterization contract is planned to include Id–Vg, Id–Vd, gm/Id, gm/gds, length scaling, DIBL, terminal small-signal admittance/capacitance, temperature sweeps, common benchmark corners, and benchmark process/mismatch Monte Carlo variation.

Technology-neutral benchmark resistor and capacitor models are included in scope so circuits can be compared without inventing process-specific passive technology for every node.

## Spectre compatibility

v1.0 is planned to include a **model-only Spectre compatibility layer**, including benchmark corners and Monte Carlo statistics. This layer is explicitly **experimental and unverified** until tested in an external Spectre environment.

Virtuoso libraries, symbols, CDFs, SKILL, ADE/Maestro setup, and other Virtuoso integration are user-managed and out of scope.

## Development specification

- [`GOAL.md`](GOAL.md) is the v1.0 completion contract for the implementation agent.
- [`AGENTS.md`](AGENTS.md) contains repository-wide engineering constraints.
- Each model kit must maintain explicit provenance and licensing metadata.

The repository is currently in initial implementation state. Do not interpret planned features as validated until the v1.0 release gates in `GOAL.md` have passed.
