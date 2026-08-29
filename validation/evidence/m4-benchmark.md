# M4 benchmark passives and observable-intent variation

Status: `validated`

Run time: 2026-08-29 16:30 UTC (2026-08-30 JST)

## Command, runtime, and immutable inputs

- Host/toolchain: validated M0 WSL2 + AlmaLinux 9.7 x86_64, ngspice 47,
  project-local OSDI artifacts
- Working compact-model families: APM130/PSP103, APM045/BSIM4, and
  APM016F/BSIM-CMG
- Command:
  `apm benchmark-check --output .apm/results/m4-benchmark-20260830c`
- Exit status: 0; report status: `validated`
- Report SHA-256:
  `f41ff2a2e3e1e45357592641b3d19d6b2a7b08f433a6f39cf167cda377ca39ae`

| Input | Schema/status | SHA-256 |
| --- | --- | --- |
| `variation/benchmark_v1.toml` | `apm.benchmark-variation.v1`, frozen | `e70794f4cee7350666f423435748dd2afe5e0980e3bc872ddce1f1b7e104ae9b` |
| `variation/adapters_v1.toml` | `apm.benchmark-adapters.v1`, real-tool calibrated | `19ec467bbfaf90065e70cb462169c3583189ec2c8039da5aaebc7ccbd4cf168d` |
| `passives/benchmark_v1.toml` | `apm.benchmark-passives.v1`, frozen | `1324d1de0a033294dedec8de58d606778e9b0fb926869066d664080681db1463` |
| `passives/ngspice/benchmark_passives.inc` | native R/C wrappers | `16d3b9f6fe0dabfac7b2d9ebf89565769708cf64a0a4a3e5862d7d96a54373c8` |
| `examples/benchmark_request.json` | `apm.benchmark-request.v1` | `167ef3a57a47c00c64d74024e4acb6c7c26943e3b9ab89e0001c358e8e31ac45` |

The result directory is intentionally untracked. It contains 143 files:
resolved samples, generated deterministic netlists, raw calibration curves,
simulator logs, and one linked `report.json`. All 40 ngspice netlist jobs
completed without warning, error, fatal, singular-matrix, failure, or
convergence text.

## Real-tool adapter calibration

Six reproducible calibration jobs each execute nine threshold raw-offset DC
sweeps and nine drive-multiplier operating points. Threshold is extracted from
terminal current with each kit's documented constant-current criterion at
`VOUT=0.8*VDD`. Drive is terminal Id magnitude at 27 degC, `L=2*Lmin`,
`VOUT=0.5*VDD`, and nominal VCTRL nearest `gm/Id=15 1/V`.

| Kit/polarity | Stored-fit max Vth residual | Stored-fit max drive residual | Nominal threshold magnitude | Nominal reference Id |
| --- | ---: | ---: | ---: | ---: |
| APM130 N | 4.86e-11 V | 5.73e-8 | 0.2742810455 V | 4.2796201 uA |
| APM130 P | 2.59e-8 V | 3.77e-7 | 0.3794177713 V | 1.6505010 uA |
| APM045 N | 2.12e-5 V | 3.65e-5 | 0.2970154870 V | 23.179103 uA |
| APM045 P | 3.12e-5 V | 1.88e-5 | 0.3223154963 V | 12.824922 uA |
| APM016F N | 1.02e-16 V | 1.86e-15 | 0.2977510227 V | 5.2727653 uA |
| APM016F P | 1.58e-16 V | 9.71e-16 | 0.2925878318 V | 3.2894128 uA |

The aggregate limits pass: maximum stored-fit residual is 31.24 uV for
threshold and 36.51 ppm fractional Id for drive. Stored versus newly measured
nominal thresholds differ by at most 0.773 nV; stored versus measured nominal
currents differ by at most `3.997e-15` relative.

The measurements confirm that raw sign is model- and polarity-specific. PSP
`delvto` raises threshold magnitude for both polarities. FreePDK45 BSIM4 uses
the opposite `delvto` sign for P. BSIM-CMG `DELVTRAND` uses the opposite sign
for both devices. PSP `factuo` and BSIM-CMG `IDS0MULT` are nearly direct drive
multipliers; FreePDK45 `MULU0` produces about 85.7% N and 89.5% P observable
fractional Id response near nominal. The resolver therefore inverts measured
fits instead of equating raw parameters.

## Statistical and deterministic behavior

The v1 synthetic severities are frozen only after the three-family calibration:
12 mV process and 8 mV reference local threshold sigma; 4% process and 2.5%
reference local drive sigma; 2% process and 1% reference local R/C scale sigma.
Fixed corners use three-sigma MOS vectors. All are explicitly comparison
severities, not foundry statistics or yield predictions.

Seed `20260830` produced and persisted process, mismatch, and all samples plus
five fixed corners. The `all` sample ID is
`sha256:fc5379fc6e0c81f6ce837c18a4020e36ae411e76c0584905f131d5e35c4ddc10`;
its file SHA-256 is
`cd8e9d08cec4c123302b8636742de5f7f93e94adbebbd366a32da615dd814dc3`.
The public CLI independently regenerated this file byte-for-byte.

The report proves:

- same request/mode/seed produces an identical resolved sample;
- seed `20260831` produces a different sample ID;
- process, mismatch, and all use the same canonical 20-draw sequence while
  applying only their documented components;
- six global process variables and every per-instance local variable are
  independent by construction;
- all three modes execute finite N/P currents in each working model family;
- rerunning the exact persisted `all` sample produces bit-identical reported
  N/P currents for all three kits;
- all resolved values in the evidence sample and five corners remain inside
  the measured raw adapter ranges;
- planar `W*L`, FinFET `NFIN*L`, and passive dimensionless matching laws use
  `1/sqrt(match_size)`; a fourfold MOS size halves local sigma for the same draw;
- every result identifies benchmark origin/mode/profile, RNG/seed where
  applicable, resolved-sample ID/path/hash, global process values, and local
  instance perturbations.

All five deterministic corner directions pass for every working family. At the
reference point, N/P current magnitudes in uA are:

| Kit | TT N/P | FF N/P | SS N/P | FS N/P | SF N/P |
| --- | ---: | ---: | ---: | ---: | ---: |
| APM130 | 4.280 / 1.651 | 7.993 / 3.049 | 2.045 / 0.794 | 7.993 / 0.794 | 2.045 / 3.049 |
| APM045 | 23.179 / 12.825 | 43.260 / 23.595 | 11.189 / 6.279 | 43.260 / 6.279 | 11.189 / 23.595 |
| APM016F | 5.273 / 3.289 | 9.616 / 6.015 | 2.481 / 1.565 | 9.616 / 1.565 | 2.481 / 6.015 |

## Passive implementation

`Rbench(value,tc1,match_size)` and `Cbench(value,tc1,match_size)` are the same
technology-neutral subcircuits for every kit. Python resolves process and local
mismatch into concrete 27 degC values, after which ordinary ngspice resistor and
capacitor primitives apply the documented linear `tc1` law.

Six process/mismatch/all simulations at 27 and 85 degC compare requested versus
measured resistor and capacitor values. The maximum relative error is
`3.442e-15`. A separate 1 kHz noise analysis measures the resolved resistor's
open-circuit noise as `1.28934723e-8 V/sqrt(Hz)` versus
`sqrt(4*k*T*R)=1.28934745e-8 V/sqrt(Hz)`, a `1.738e-7` relative difference.
This verifies that the wrapper retains native resistor Johnson-noise physics and
does not reimplement it.

## Tests, gates, and scope

Ruff passes and all 35 repository tests pass. Tests cover frozen placeholder-free
specifications, request validation, deterministic seeds, mode composition,
process/local separation, exact sample hash verification, non-destructive
persistence, planar/FinFET/passive matching laws, fourfold-size sigma scaling,
raw sign mappings, passive temperature/composition, and invalid geometry/scale
rejection. REUSE lint passes.

This evidence completes M4 and validates release gate `passives.benchmark`.
Gate `variation.benchmark` is deliberately not claimed yet: its contract
requires every kit, while APM022 and APM350 are subsequent milestones. Their
adapters must be independently calibrated and exercised by the same validator.
IHP-native variation is also separate M8 work. Spectre benchmark statistics
remain experimental/unverified M9 work.
