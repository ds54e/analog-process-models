# M10 release validation evidence

- Gate / milestone: M10 licensing/provenance audit, clean-clone validation,
  release review, and all 16 gates in `validation/release_gates.toml`
- Status: `validated`
- Execution: 2026-08-29 18:38–18:42 UTC (2026-08-30 JST)
- Validated Git commit: `74389a5e1dc241c390c501a3b74c27be07bdbe7e`
- Fresh clone:
  `/home/admin/src/apm-v1-clean-IN1XjOZk/analog-process-models`
- Environment: WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`, AlmaLinux
  9.7, x86_64, `/dev/sdd` ext4 Linux filesystem, outside `/mnt/c`

## Clean-clone procedure

The directory was created by a new network clone of the authoritative origin.
Before any bootstrap command, `python3 tools/attest_clean_clone.py` observed an
empty Git status and no `.apm/` directory, then bound the origin, absolute clone
path, platform, and exact commit into the ignored attestation.

The documented sequence was then run without copying any tool, model binary,
or result from the development checkout:

```text
git clone https://github.com/ds54e/analog-process-models.git <fresh-path>
python3 tools/attest_clean_clone.py                         # exit 0
tools/bootstrap-el9.sh                                      # exit 0
tools/setup-python.sh                                       # exit 0
.venv/bin/apm build-models                                  # exit 0
.venv/bin/apm doctor                                        # exit 0
.venv/bin/apm validate --output .apm/results/clean-clone-static
                                                            # exit 0
.venv/bin/apm validate --release \
  --output .apm/results/release-74389a5                     # exit 0
.venv/bin/apm compare apm045 apm022 \
  --output .apm/review/planar-pair                          # exit 0
.venv/bin/apm compare apm022 apm016f \
  --output .apm/review/planar-finfet-pair                  # exit 0
git status --porcelain --untracked-files=all                # empty
```

The bootstrap built ngspice 47 with `--enable-predictor --enable-osdi` and
OpenVAF-ReLoaded tag `v24.0.2mob`/commit
`fdf2522b70f42793f64b1c72f0195c96dea0cc19` against project-local AlmaLinux
LLVM 20.1.8 and Rust 1.98.0. It then compiled PSP103 QS, PSP103 NQS, and
BSIM-CMG 112.1.0 OSDI artifacts from the vendored sources. Package and runtime
versions both reported `1.0.0`.

## Observed release result

The `apm.release-validation.v1` report recorded `status=pass`, target
`v1.0.0`, `required_gate_count=16`, and `passed_required_gate_count=16` at the
attested commit. Every component ran during that one command:

| Component | Status | Duration | Report SHA-256 |
| --- | --- | ---: | --- |
| exact-commit clean clone | verified | 0.009 s | `db70c4e2ebcbfaf11411cd17c2d7ad595f5bd08ca0f4e3e59a8a76fa0e367231` |
| static/regression audits | pass | 1.079 s | `6f34b7470ae0cf1e786f4ec1359609da0cb5337c368ff5e6c610fea503f61b8d` |
| ngspice/OSDI doctor | pass | 28.172 s | `0de0792bcfbab783e5731214fc78176a987f682ae059c495be36f6cd9f7ebfc8` |
| benchmark variation/passives | validated | 1.474 s | `8b10b034c1b90d06ea5e8fcd90c8a8788d7236385a2359e8b9827507973c3014` |
| APM130 native variation | validated | 14.951 s | `5919525b39dfb7a1a822aa119c7543b181b7b1bee6edfeab969405f5f4321e52` |
| all-kit characterization/comparison | validated | 12.671 s | `7bfab75b7d824f7ad79aa710e4cfa0923d8e487bb5a9b8c954d2f9cffce5ed3b` |

The top-level release report SHA-256 is
`24e79ee766685ec336d0cb572b23e405fba5a6dd7723146b8294dc4bdbfad66f`.

Specific observations:

- all four doctor devices simulated headlessly: native BSIM3, native BSIM4,
  PSP103 OSDI, and BSIM-CMG OSDI;
- 58 Pytest tests, Ruff, and REUSE 5.1.1 passed; REUSE covered 134/134 files
  with Apache-2.0, ECL-2.0, and the preserved Si2 PSP license reference;
- all five exact-file provenance manifests passed, including complete vendored
  filesystem coverage, expected license sets, preserved notices, and generated
  APM130 Spectre-card provenance;
- the tracked distribution had no unresolved/remote model include, generated
  OSDI/raw/log/result artifact, oversized artifact, suspicious credential
  filename, or detected credential signature;
- package, installed distribution, runtime, release target, and changelog all
  identified `1.0.0`, with no forbidden release-critical placeholder token;
- benchmark corners, deterministic process/mismatch/all replay, calibrated
  observable adapters, Rbench/Cbench values, and native resistor noise passed;
- all five IHP corner profiles and 128-sample process/mismatch cohorts passed
  their global/local, replay, spread, independence, and area-scaling checks;
- complete current-run characterization produced the required results for all
  five kits and both polarities, with a 10-row normalized comparison whose CSV
  SHA-256 is
  `78177cad910c3a02cfa0ddb57fd1ae7a4a813e7827b04505e6806758ac824748`;
- the APM045/APM022 planar comparison passed with the same per-width basis;
  its report SHA-256 is
  `0d07ba90ae815cc40157b750bb169013458f985500602e19f32bf7ca82ad2efd`;
- the APM022/APM016F planar/FinFET comparison passed and correctly left
  cross-basis current/capacitance ratios null; its report SHA-256 is
  `eacb9483615490836117134af3b3aff444cc0402ae89db6eff17580ad1625b3a`;
  and
- the manual claim record and reviewed-file hashes passed, with no repository
  visibility change, foundry/silicon-correlation claim, or real-Spectre claim.

## Evidence boundary

Spectre remains `structurally_checked` and backend status remains
`experimental_unverified`; no Spectre executable was available, parsed a file,
or simulated a model. That is the required v1.0 boundary, not a waiver.

The post-validation commit adds only compact release evidence/status/review
material and binds this evidence file into the hash-checked claim audit. Before
tagging, the exact commit containing this file must itself pass a new attested
fresh-clone `apm validate --release`. The annotated `v1.0.0` tag message records
that final commit and final report hash without mutating the validated tree.
