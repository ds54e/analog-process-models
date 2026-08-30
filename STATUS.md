# APM v2.0.0 implementation status

This is the compact persistent progress index. It is not validation evidence by
itself; authoritative gates come from `validation/release_gates.toml`.

## Overall state

- Project: Analog Process Models (APM)
- Repository: `https://github.com/ds54e/analog-process-models`
- Historical baseline: `v1.0.0` at
  `e7bba6aaba1487a1116459a6b7b2c3c5add93318`
- Target: `v2.0.0`
- State: `V2_RELEASE_CANDIDATE_INTEGRATION`
- Current milestone: V2-M9 exact-commit clean-clone validation
- Release eligible: **NO** until the final fresh-clone report passes all 20
  required gates
- Blockers: none recorded

Historical v1 evidence is useful baseline context only and cannot satisfy a v2
gate.

## Reference toolchain in use

The current WSL2 + AlmaLinux 9.7 x86_64 workspace has verified:

- Python 3.9.25;
- ngspice 47 built with OSDI and predictor support;
- project-local OpenVAF-Re-Loaded v24.0.2mob;
- native BSIM3 and BSIM4 execution;
- PSP103 OSDI execution; and
- BSIM-CMG 112.1.0 OSDI execution.

Development may reuse this verified state. The release still requires a new
clone, pre-bootstrap attestation, project-local bootstrap, rebuild, and complete
rerun at the exact release commit.

## Family matrix

| Technology | Families | Implementation state |
| --- | --- | --- |
| APM350 | `general` | Manifest-driven family, native BSIM3, characterization and benchmark pass |
| APM130 | `lv`, `hv` | Audited IHP PSP103 families, comparison, benchmark, and independent native cohorts pass |
| APM045 | `vtl`, `vtg`, `vth`, `thkox` | All four audited BSIM4 families and both comparison sets pass |
| APM022 | `lvt`, `svt`, `hvt` | Independent VTH0-isolated variants, ordering, characterization, and benchmark pass |
| APM016F | `lvt`, `svt`, `hvt` | Independent PHIG-only BSIM-CMG variants, ordering, NFIN, characterization, and benchmark pass |

Catalog total: five technologies, 13 Electrical Families, and 26 public
family-qualified devices.

## Milestones

| Milestone | Status | Evidence / result |
| --- | --- | --- |
| V2-M0 Domain/catalog migration | VALIDATED | Declarative technology/family/backend manifests, generic fixture-family tests, and no v1 runtime SSOT/alias dependency |
| V2-M1 APM130 LV/HV | VALIDATED | `validation/evidence/v2_apm130_native.json` |
| V2-M2 APM045 VTL/VTG/VTH/THKOX | VALIDATED | All-family real-tool run and `validation/evidence/v2_comparisons.json` |
| V2-M3 Characterization/result/comparison v2 | VALIDATED | 13-family real-tool run and `validation/evidence/v2_comparisons.json` |
| V2-M4 Benchmark Global/Local/All | VALIDATED | `validation/evidence/v2_benchmark_adapters.json` |
| V2-M5 APM022 multi-VT | VALIDATED | Independent provenance, all-temperature ordering, benchmark, and comparison evidence |
| V2-M6 APM016F multi-VT | VALIDATED | Independent provenance, genuine BSIM-CMG/NFIN, benchmark, and comparison evidence |
| V2-M7 Integrated all-family validation | VALIDATED | Real ngspice all-family, five-anchor, four within-technology comparison jobs, benchmark, and native variation |
| V2-M8 Spectre/provenance/docs | VALIDATED | `validation/evidence/v2_spectre_structural.json`, `v2_provenance.json`, rewritten public docs, and hash-bound claim review |
| V2-M9 Release validation | IN_PROGRESS | Requires committed/pushed exact clone, attestation, bootstrap, all 20 gates, and only then the v2.0.0 tag |

Status values are `NOT_STARTED`, `IN_PROGRESS`, `VALIDATED`, and `BLOCKED`.

## Frozen implementation decisions

- Runtime discovery and dispatch are driven by `technology.toml`,
  `family.toml`, and backend `binding.toml` manifests.
- Canonical identity is `technology_id/family_id/device_id`.
- Planar public sizing is `w,l`; FinFET sizing is `l,nfin`; no common
  multiplicity/finger interface exists.
- APM045 THKOX uses an APM-selected 2.0 V native behavior profile and an
  explicitly simulated 1.0 V VTG/THKOX common overlap.
- APM130 LV/HV uses upstream 1.2/3.3 V native profiles and a 1.2 V comparison
  overlap.
- APM022 LVT/HVT vary only polarity-correct VTH0 by −0.08/+0.10 V threshold
  intent around independently authored SVT.
- APM016F LVT/HVT vary only polarity-correct PHIG with 0.10 eV spacing around
  independently authored SVT.
- SS uses fixed method
  `apm.ss.threshold_relative_two_decade_linear_fit@1.0.0`: 0.003–0.3 of the
  threshold criterion, 0.05 V drain bias, at least five OLS points, R² ≥ 0.995.
- Generated characterization netlists set `gmin=1e-15 S`.
- Benchmark Global sigma is 12 mV Vth and 3% drive; Benchmark Local reference
  sigma is 8 mV and 2.5%, with explicit planar/FinFET/passive size laws.
- Benchmark Global shares observable latents across sibling families by
  technology/polarity/intent; this is not a physical correlation claim.
- IHP-native LV/HV cohorts remain independent, retain upstream profile
  semantics, and do not invent a native All mode.
- Spectre covers all families structurally but remains model-only
  experimental/unverified.

## Latest checks

Completed development checks on 2026-08-30 include:

- all 13 families and 26 devices characterized by real ngspice at −40, 27, 85,
  and 125 °C with finite-difference gm/gds, Ion/Ioff/log ratio/SS, raw signed
  currents, and both 4×4 complex-Y bias views;
- five cross-process anchors plus APM045 threshold/gate-stack and
  APM022/APM016F multi-VT comparisons, all `apm.comparison.v2` validated;
- all family/device Benchmark Global/Local/All adapters, five fixed corners,
  deterministic PCG64 replay, local size scaling, passives, temperature, and
  resistor noise;
- independent 128-sample IHP-native LV and HV process/mismatch cohorts plus
  corners and replay;
- all-family deterministic Spectre generation/structure with no real-tool,
  parse, or numerical claim;
- 57 Pytest tests passing; and
- complete staged model provenance, tracked-distribution, REUSE, catalog,
  migration, metadata, and hash-bound claim audits passing.

## Release gate state

The release evaluator implements the exact 20 IDs in
`validation/release_gates.toml` and rejects a missing, skipped, evidence-free,
or failed gate. Package/runtime metadata now identifies 2.0.0.

No final v2 release gate is claimed yet. V2-M9 will run the full validator in a
fresh exact-commit clone; `v2.0.0` must not be tagged unless that report shows
20/20 required gates passed with valid evidence.
