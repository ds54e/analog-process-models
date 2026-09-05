# Analog Process Models

Analog Process Models (**APM**) provides MOS compact models and ngspice-based tools
for analog circuit research. Use the models in your own circuits, characterize
devices, compare electrical families and technology classes, and study stationary
noise and supported variation models.

The collection combines redistributed open models with APM-authored generic models.
It is a research toolkit, **not a manufacturable PDK**. Model provenance, supported
ranges and the limitations of each study are documented alongside the tools.
This repository is the APM project; APM always means Analog Process Models here.

Current `main` is the v6 development/candidate line. V6 reorganizes documentation,
validation and historical reproduction while preserving v5 scientific models,
source coefficients and public result semantics. See [status](STATUS.md) for actual
qualification results and [migration](docs/history.md) for changed maintainer
workflows. Creating or publishing a v6 release requires separate approval.

## Model overview

The manifest catalog contains **five technologies, fifteen electrical families and
thirty public MOS devices**. Every family has N/P devices. An electrical family
identifies a nominal model parameterization; an Operating Profile chooses conditions
for a study. Neither a family name nor a profile voltage is a reliability rating.

| Technology | Electrical families | Origin | ngspice implementation |
| --- | --- | --- | --- |
| APM350 | `general` | APM-authored generic | Native BSIM3 |
| APM130 | `lv`, `hv` | Pinned IHP SG13G2 MOS subset | PSP103 via OSDI |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` | Audited FreePDK45 nominal cards | Native BSIM4 |
| APM045 | `io18`, `io25` | APM-authored generic | Native BSIM4 |
| APM022 | `lvt`, `svt`, `hvt` | APM-authored generic | Native BSIM4 |
| APM016F | `lvt`, `svt`, `hvt` | APM-authored parameters; licensed BSIM-CMG engine | BSIM-CMG via OSDI |

Public transistor terminals are `d g s b`. Planar devices use `w,l`; FinFET devices
use `l,nfin` with integer NFIN. There is no invented common effective width or
universal compact-model parameter API. Public wrapper names include the family,
for example `apm045_vtg_nmos` and `apm016f_svt_nfet`.

The manifests and [model/source guide](docs/models.md) describe each family's
origin and support. [THIRD_PARTY.md](THIRD_PARTY.md) preserves file-level licensing,
source revisions, adaptation credit and required acknowledgements. Model sources
are shipped locally; generated OSDI binaries are built in ignored project state.

## Start a useful study

The reference environment is x86_64 WSL2 with RHEL-compatible EL9 Linux, ngspice 47
and a project-local pinned OpenVAF compiler. Keep builds and results on the Linux
filesystem. [Getting started](docs/getting-started.md) covers external prerequisites,
a cold build in an empty prefix, verified reuse and a first real result. Returning
users should preserve their verified toolchain and reconcile editable Python
metadata after updating the source.

Once configured, discover a device from the repository root:

<!-- apm-journey: discover -->
```bash
.venv/bin/apm list technologies
.venv/bin/apm list families apm045
.venv/bin/apm describe apm045/vtg/nmos
```

Inspect the printed selector, public name, geometry and backend binding. Discovery
reports the model catalog; it does not execute a simulator or establish physical
accuracy. The task guides below give executable commands, output locations, fields
to inspect and the corresponding interpretation limits.

| Task | Start here |
| --- | --- |
| Put nominal MOS devices in your own circuit | [Using models](docs/using-models.md) |
| Measure Id–Vg, gm/gds, capacitance and compare families | [Characterization](docs/characterization.md) |
| Inspect stationary PSDs, fits and unavailable states | [Device noise](docs/noise.md) |
| Choose synthetic, native or source-transfer variation | [Variation overview](docs/variation.md) |
| Save one Research Local realization and replay it | [Research Local](docs/research-local.md) |

Characterization retains signed terminal currents, finite-difference gm/gds and
complete complex terminal Y matrices. Comparison views preserve native geometry
and normalization: current or capacitance per width is not silently equated with
per-fin values. Stationary-noise outputs retain effective parameter provenance and
actual external transfer. They characterize existing compact-model predictions,
not calibrated process noise. Unreachable bias targets and unavailable fits remain
explicit states instead of fabricated values.

Benchmark Global/Local/All are synthetic comparison stresses. APM130 native
corner/process/mismatch follows the selected IHP libraries. APM045 VTG Research
Local supports N/P at W=1–4 um and L=0.12–0.40 um with a 300 K statistical anchor.
Its Hart/TSMC40 adaptation is a transfer hypothesis; original Hart/ST40 beta remains
blocked. IO18/IO25 have unresolved assessments and no default statistical profile.
These flows do not establish all-family measured Monte Carlo or foundry yield.

## Support and maintenance

APM supplies no layout, PCells, DRC/LVS/PEX, standard cells, signoff or reliability
qualification. Operating voltages are study profiles. Spectre files are
[model-only experimental/unverified](docs/spectre.md); real Spectre parsing,
numerical equivalence and Virtuoso automation are not claimed. Detailed boundaries
are in the [models guide](docs/models.md) and [APM045 positioning](APM045_POSITIONING.md).

[All guides](docs/index.md) link to current scientific contracts.
[Maintainers](docs/maintainers/index.md) have separate current checks, real-tool
regressions and release qualification. [History operations](docs/history.md) verify
and export exact source/evidence without executing old code or changing a checkout.
Normal model use does not require Git history; strict historical auditing does.
Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md); security and provenance
concerns follow [SECURITY.md](SECURITY.md).
