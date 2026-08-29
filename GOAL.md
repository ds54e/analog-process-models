# APM v1.0 Implementation Goal

Build and release **Analog Process Models (APM) v1.0.0** as a self-contained, open compact-model collection and characterization framework spanning mature planar CMOS through FinFET.

Work autonomously until the Definition of Done is satisfied. Do not stop at scaffolding, planning, or partial implementation. Research authoritative public sources as needed, implement, simulate, validate, fix failures, audit licensing, document limitations, and leave the repository release-ready.

## 1. Purpose

Provide five simulation technology kits:

| Kit | Technology | Architecture | Compact model |
| --- | --- | --- | --- |
| APM350 | 0.35 µm-class | planar bulk | BSIM3-class |
| APM130 | 130 nm | planar bulk | PSP103 |
| APM045 | 45 nm | planar bulk | BSIM4 |
| APM022 | 22 nm-class | planar bulk | BSIM4 |
| APM016F | 16 nm-class | FinFET | BSIM-CMG |

APM is **not a manufacturable PDK**. Do not implement layout, PCells, DRC, LVS, PEX, extraction, standard cells, signoff, or foundry correlation claims.

## 2. Reference platform

Validated v1.0 reference environment:

- WSL2
- RHEL-compatible EL9 Linux
- x86_64
- ngspice with OSDI support
- Python 3
- OpenVAF-ReLoaded when Verilog-A/OSDI compilation is needed
- xschem optional, examples only

Native Windows and macOS support are out of scope. Keep build/run data on the WSL Linux filesystem, not `/mnt/c`.

Automated characterization must be headless and must not depend on xschem, `~/.spiceinit`, or other user-global simulator state.

## 3. Model-kit requirements

### APM350

Use a clearly redistributable open generic 0.35 µm-class model. Current preferred reference is the open SCN4M_SUBM-class source, subject to exact file-level license verification.

Represent metadata honestly. If the selected model has a minimum modeled length near 0.4 µm, record both the 0.35 µm technology class and the actual model minimum length.

Do not claim foundry correlation.

### APM130

Use the simulation subset of the IHP SG13G2 Open PDK needed for low-voltage NMOS/PMOS operation.

Use PSP103 and preserve exact upstream provenance and licenses.

Support on the validated ngspice side:

- nominal
- APM benchmark corners
- APM benchmark process/mismatch/all variation
- available IHP-native corners
- available IHP-native process variation
- available IHP-native mismatch variation

Keep PDK-native and APM benchmark variation visibly distinct.

### APM045

Use a clearly redistributable, open-source-clean FreePDK45 simulation-model subset. Prefer the Chips4Makers clean source if file-level license verification confirms redistribution.

Do not vendor layout, Calibre, SVRF, or unrelated physical-design assets.

### APM022

Use an **APM-authored** BSIM4 parameter deck.

Do not copy, modify, interpolate, or numerically derive the parameter deck from official PTM22 model-card parameters. PTM may only be used locally as a non-redistributed comparison oracle.

Create the deck independently using public literature, BSIM4 model semantics, published representative technology characteristics, and explicit APM behavioral requirements.

Label it clearly as:

- `model_origin = apm_generic`
- not foundry-correlated
- not PTM-derived

Required qualitative behavior includes stronger short-channel effects than APM045, larger DIBL near minimum length, lower intrinsic gain near minimum length, lower-voltage operation, higher speed/current capability, and sensible capacitance behavior.

### APM016F

Use a pinned, legally redistributable BSIM-CMG implementation from an authoritative open source. Preserve the exact upstream license text; do not relicense vendor code.

The APM016F parameter deck itself must be APM-authored and must not be numerically derived from PTM-MG16 model-card parameters. PTM-MG may be used only as a local comparison oracle.

Required behavior:

- genuine FinFET / multi-gate model execution
- discrete `NFIN` sizing
- Id and gm scale sensibly with NFIN
- improved electrostatic control relative to APM022
- sensible threshold roll-off, DIBL, output conductance, and capacitance

Disable self-heating in v1.0 unless basic model operation requires otherwise.

## 4. Public device interface

Keep the public simulation interface intentionally small.

Planar devices expose only:

- terminals: `d g s b`
- parameters: `w`, `l`

FinFET devices expose only:

- terminals: `d g s b`
- parameters: `l`, `nfin`

Do not expose common v1.0 public parameters for multiplicity, finger count, `nf`, `ng`, or layout semantics. Parallel devices can be represented as separate instances.

Do not invent a universal effective-width abstraction across planar and FinFET devices.

## 5. Benchmark passives

Every kit must support identical technology-neutral benchmark passives:

- `Rbench(value, tc1, match_size)`
- `Cbench(value, tc1, match_size)`

`match_size` is dimensionless benchmark matching size, not physical layout area.

Local benchmark mismatch scales approximately as `1/sqrt(match_size)`.

Resolve variation to concrete values, then use normal simulator resistor/capacitor primitives. Do not reimplement resistor Johnson-noise physics.

Technology-native passives are optional and are not a v1.0 release requirement.

## 6. Characterization contract

Implement the same terminal-level measurements for every technology.

Required raw characterization:

- Id–Vg
- Id–Vd
- terminal small-signal complex Y matrix

Required derived characterization:

- gm/Id
- gm/gds
- length scaling
- DIBL
- derived capacitance matrix, including at least Cgg, Cgd, and Cgs

Required temperatures:

- -40 °C
- 27 °C
- 85 °C
- 125 °C

Use normalized comparison coordinates where appropriate:

- `L/Lmin`
- `VDS/VDD`
- `gm/Id`

Provide native/raw views and normalized cross-technology views. Do not use identical absolute W or VGS as the primary cross-process comparison method.

## 7. gm and gds

Simulator-internal OP field names are not the canonical API.

Canonical values come from terminal finite differences:

- `gm = dId/dVg`
- `gds = dId/dVd`

Use central differences and numerical convergence checks with more than one perturbation size.

Native simulator gm/gds may be used as validation oracles. For APM130, explicitly compare derived quantities with PSP native OP values to validate the methodology.

## 8. DIBL

Use a documented constant-current threshold method.

Default drain voltages:

- `VDS_low = 50 mV`
- `VDS_high = 0.8 * nominal VDD`

Compute:

`DIBL = (Vth_low - Vth_high) / (VDS_high - VDS_low)`

Use technology-appropriate threshold-current normalization: planar devices by W/L, FinFET devices by NFIN. Store the exact extraction convention in result metadata.

## 9. Capacitance

Do not use compact-model-specific `cgg/cgd/cgs` OP names as the canonical API.

Use AC analysis to obtain terminal admittance. Store the complex Y matrix as raw data and derive capacitance quantities from its imaginary terms.

Check that the selected quasi-static characterization frequency does not materially change extracted capacitance over a reasonable low-frequency range.

MOS noise characterization is out of scope for v1.0, but the design must not prevent adding it later.

## 10. APM benchmark variation

Provide one technology-neutral benchmark variation model across all five kits.

Required modes:

- process
- mismatch
- all = process + mismatch

Canonical MOS variation intents:

- `vth_shift`
- `drive_shift`

These are observable-level semantics, not raw compact-model parameters.

`vth_shift` means a target threshold-behavior shift.

`drive_shift` means a target relative Id change at a defined reference bias.

Investigate and validate technology-specific mappings, likely including:

- BSIM3/BSIM4: `delvto`, `mulu0` or equivalents
- PSP: `delvto`, `factuo` or equivalents
- BSIM-CMG: `DELVTRAND`, `IDS0MULT`, `U0MULT` or equivalents

Do not assume equal raw parameter percentages mean equal observable shifts.

Calibrate drive mapping per kit at a documented reference point, e.g. approximately `L=2*Lmin`, `VDS=0.5*VDD`, `gm/Id≈15 V^-1`. Store calibration metadata.

Do not freeze benchmark sigma/severity values until representative kits are operational and the impact is characterized.

## 11. Benchmark mismatch law

Use an explicitly synthetic APM matching law.

Planar:

`match_size = (W*L)/(Wref*Lref)`

FinFET:

`match_size = (NFIN*L)/(NFINref*Lref)`

Local benchmark sigma:

`sigma_local = sigma_ref / sqrt(match_size)`

Never describe this as a foundry Pelgrom model or a silicon-yield prediction.

## 12. Benchmark corners

Provide common deterministic corners:

- `bench_tt`
- `bench_ff`
- `bench_ss`
- `bench_fs`
- `bench_sf`

Define them from fixed benchmark-variation vectors. Keep them distinct from native PDK/model corners.

Native corners may be exposed separately where they exist.

## 13. ngspice Monte Carlo

For APM benchmark variation, generate randomness in Python outside the compact model.

Generate a machine-readable resolved variation sample containing global/local MOS and R/C perturbations, then perform deterministic ngspice simulation.

Requirements:

- explicit seed handling
- same seed reproduces identical benchmark samples
- different seeds differ
- machine-readable sample persistence

Do not rely on Verilog-A random-number functions for APM benchmark variation.

IHP-native variation is a separate model-owned flow.

## 14. Spectre model-only compatibility

v1.0 must include Spectre-compatible **model files only**.

Status must be prominently labeled:

**EXPERIMENTAL / UNVERIFIED**

because Spectre is not available during initial development.

Include:

- nominal model interface
- benchmark corners
- benchmark R/C
- benchmark process MC
- benchmark mismatch MC
- benchmark all MC
- documentation

Do not include:

- Spectre testbenches
- SKILL
- CDF
- symbols
- OA libraries
- ADE/Maestro states
- OCEAN
- Virtuoso automation

Virtuoso integration is fully user-managed.

Use native Spectre BSIM3/PSP/BSIM4/BSIM-CMG implementations where practical.

Prefer thin Spectre subckt wrappers as the public MOS interface so local mismatch can be applied cleanly per instance.

Use Spectre `statistics` blocks so standard Spectre/ADE Monte Carlo can select Process, Mismatch, or All.

For APM130 Spectre support, APM benchmark variation is required; IHP-native Monte Carlo compatibility is not claimed for v1.0.

## 15. xschem

xschem is optional. Provide only a small set of useful example schematics for discoverability and manual exploration.

The automated framework must not depend on GUI operation.

## 16. Self-contained distribution

The repository must contain every technology model asset required for all five kits.

Users must not need separate transistor-model downloads for PTM, FreePDK45, IHP, or BSIM model sources.

Normal software dependencies such as ngspice, Python, OpenVAF-ReLoaded, and optional xschem may remain external.

Prefer building OSDI locally from redistributable source rather than committing generated OSDI binaries.

## 17. Licensing and provenance

Licensing correctness is a v1.0 release requirement.

APM-authored project code and APM-authored parameter decks may use Apache-2.0.

Do not relicense third-party model sources.

Use SPDX/REUSE-compatible file-level metadata where practical.

Maintain:

- `LICENSES/`
- `THIRD_PARTY.md`
- `REUSE.toml` or equivalent
- per-kit `provenance.toml`

For imported model assets record upstream project, URL, exact revision, original license, imported files, modifications, and useful checksums.

If redistribution rights for any file are ambiguous, do not ship it. Replace it with an APM-authored model or a clearly redistributable source.

## 18. CLI and workflow

Keep the CLI small. Provide equivalents of:

- `apm doctor`
- `apm build-models`
- `apm characterize <technology>`
- `apm validate`
- `apm compare <technology-a> <technology-b>`

Exact names may be simplified if justified.

`apm doctor` should perform real simulator/model smoke tests where practical, not only file-presence checks.

## 19. Testing

Prefer robust property-based regression over brittle exact-number assertions.

Test properties such as:

- sane NMOS/NFET and PMOS/PFET polarity
- finite, physically sensible results in supported bias ranges
- increasing planar L generally improves gm/gds in appropriate operating regions
- NFIN increase gives sensible FinFET current scaling
- benchmark mismatch sigma decreases with match_size
- fourfold match_size gives approximately half local sigma
- seed reproducibility
- sensible benchmark-corner ordering
- numerical convergence of finite-difference gm/gds
- reasonable APM130 agreement between derived and PSP native gm/gds

Small upstream numerical changes should not fail the suite solely because exact snapshots moved. Reference snapshots may be used for warnings/review.

## 20. Development order

Proceed approximately in this order unless empirical evidence requires adjustment:

1. **M0 Runtime qualification** — WSL2/EL9, ngspice/OSDI; smoke BSIM3, PSP103, BSIM4, BSIM-CMG.
2. **M1 APM130** — establish the measurement methodology using a real open model.
3. **M2 APM045** — ensure the implementation is not PSP-specific.
4. **M3 APM016F** — introduce genuine FinFET/BSIM-CMG geometry early.
5. **M4 Benchmark R/C and benchmark variation** across working model families.
6. **M5 APM022** — independently author and validate a scaled-planar deck.
7. **M6 APM350** — add the long-channel anchor.
8. **M7** — complete DIBL, Y-matrix capacitance, temperature, and benchmark corners for all kits.
9. **M8** — complete IHP-native corners/process/mismatch on the ngspice reference side.
10. **M9** — add experimental Spectre model-only files with benchmark MC.
11. **M10** — full licensing/provenance audit, clean-clone validation, release review.

## 21. v1.0.0 Definition of Done

Do not declare completion until all are true:

### Packaging
- All five kits are present.
- No separate transistor-model download is required.
- Every vendored file has auditable provenance/license information.

### Reference runtime
- Clean setup works on WSL2 + EL9-compatible Linux.
- Headless ngspice simulation works.
- PSP103 OSDI works.
- BSIM-CMG OSDI works.

### Devices
- Every kit has usable N/P devices with the defined public interface.

### Characterization
Every kit completes:
- Id–Vg
- Id–Vd
- gm/Id
- gm/gds
- length scaling
- DIBL
- terminal Y matrix / capacitance
- required temperature sweep

### Passives
- Rbench and Cbench work identically across all kits.

### Benchmark variation
Every kit supports:
- benchmark corners
- benchmark process MC
- benchmark mismatch MC
- benchmark process+mismatch MC

with reproducible ngspice benchmark sampling.

### Native IHP variation
- APM130 supports the selected available IHP-native corners/process/mismatch flow in the ngspice reference implementation.

### FinFET integrity
- APM016F genuinely uses BSIM-CMG and NFIN-based sizing; it is not a planar model behind a FinFET-looking interface.

### Spectre
- Model-only Spectre artifacts exist for every kit and include benchmark MC design.
- They are clearly labeled experimental/unverified.
- Actual Spectre validation is not required for v1.0.

### Documentation
README documents scope, installation, model provenance, fidelity limitations, benchmark vs native variation, benchmark passives, comparison methodology, Spectre status, and the non-manufacturable-PDK disclaimer.

### Release readiness
- tests pass
- license audit passes
- clean-clone validation passes
- no accidental credentials, scratch data, generated binaries, or model files with unclear redistribution rights are committed
- release notes/changelog are ready

## 22. Explicit non-goals for v1.0

Do not implement:

- layout / PCells
- DRC / LVS / PEX / extraction
- standard cells / P&R
- silicon signoff
- MOS noise characterization
- HBT/BJT models
- inductors / varactors / RF models
- AMS co-simulation
- native Windows support
- macOS support
- Virtuoso symbols/CDF/SKILL
- ADE/Maestro automation

Do not expand scope because an upstream project supports related functionality.

## 23. Autonomy boundaries

High autonomy is desired. Do not ask for confirmation for routine in-scope implementation decisions, local dependency installation inside the designated WSL environment, refactoring, testing, research, or failure repair.

Do not:

- copy or redistribute files with unclear licensing
- commit credentials/tokens/secrets/proprietary models
- modify unrelated user data or repositories
- weaken tests merely to make CI green
- claim Spectre validation that was not performed
- claim foundry accuracy or silicon correlation for generic/predictive APM models
- silently substitute an easier requirement when a required item fails

If blocked, investigate alternatives and continue. Prefer a smaller correct implementation over a speculative framework. Record material deviations in repository documentation.

## 24. Final review

Before declaring v1.0 ready:

1. Perform a fresh clean-clone setup.
2. Build required local compact-model artifacts.
3. Run the complete validation suite.
4. Run representative comparisons across all five technologies.
5. Audit every vendored file's license/provenance.
6. Review README claims against actual tested behavior.
7. Verify all Spectre artifacts are marked experimental/unverified.
8. Remove obsolete experiments, scratch outputs, temporary downloads, and dead code.
9. Ensure a new user can reproduce the project without reading development history.
10. Only then prepare/tag v1.0.0.
