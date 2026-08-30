# APM v2.0.0 release-readiness evidence

Gate / milestone: V2-M8 public-claim/provenance integration and V2-M9 release
candidate preparation

Status: release-candidate implementation complete; exact-commit clean-clone
release gate pending

Date: 2026-08-30

## Implemented release surface

The implementation exposes five manifest-discovered technologies, 13
Electrical Families, 26 family-qualified devices, catalog-driven
characterization/comparison, Benchmark Global/Local/All, independent IHP-native
APM130 LV/HV variation, technology-neutral benchmark passives, and model-only
Spectre artifacts for every family.

The release evaluator implements the exact 20 required IDs in
`validation/release_gates.toml` and fails closed when any required gate is
missing, unimplemented, skipped, failed, evidence-free, or points to missing
evidence.

## Development evidence completed

Real ngspice 47 development runs completed for:

- native BSIM3/BSIM4, PSP103 OSDI, and BSIM-CMG OSDI device smokes;
- all 13 family characterizations at four temperatures;
- five cross-process anchors;
- APM045 threshold and native/common-overlap gate-stack views;
- APM022 and APM016F threshold views and Vth/Ion/Ioff ordering;
- all 13-family/26-device Benchmark Global/Local/All adapters, corners,
  deterministic replay, matching-size scaling, Rbench/Cbench temperature, and
  resistor noise; and
- independent IHP-native APM130 LV/HV corners plus 128-sample process and
  mismatch cohorts.

Compact summaries are:

- `validation/evidence/v2_comparisons.json`;
- `validation/evidence/v2_benchmark_adapters.json`;
- `validation/evidence/v2_apm130_native.json`; and
- `validation/evidence/v2_spectre_structural.json`; and
- `validation/evidence/v2_provenance.json`.

The complete implementation regression suite reported 57 passing tests after
documentation integration. Ruff, Python compilation, REUSE, exact provenance,
tracked-distribution, catalog, migration, metadata, and claim audits pass on
the staged candidate tree.

## Licensing and distribution readiness

Each shipped model source/manifest/wrapper/generation asset is enumerated and
hash-declared by its technology provenance manifest. Imported IHP, FreePDK45,
PSP/JUNCAP, and BSIM-CMG assets preserve their exact upstream licensing
boundaries and notices. APM022 and APM016F generation records enforce their
independent-authorship and PTM/PTM-MG exclusion boundaries.

Generated OSDI binaries, toolchain sources, raw simulation data, and detailed
reports remain untracked. Every runtime model include is local; a source clone
requires no separate transistor-model download.

## Claim boundaries reviewed

APM is not a manufacturable PDK. APM-authored generic decks make no foundry or
silicon-correlation claim. Benchmark Global sibling-family sharing is a
synthetic observable stress contract, not physical process correlation.
Operating Profiles do not imply reliability ratings.

Spectre has not run in the reference environment. Its artifacts are model-only
experimental/unverified; structural checking does not claim parse validity,
numerical conformance, or compatibility with a particular Spectre version.

## Final evidence condition

This file records readiness and development milestones; it does not substitute
for V2-M9. The authoritative final evidence must come from an untouched,
attested WSL2 + RHEL-compatible EL9 x86_64 clone at the exact candidate commit,
after documented bootstrap. The final
`apm validate --release --output .apm/results/v2-release` report must show:

```text
schema: apm.release-validation.v2
target: v2.0.0
status: pass
required_gate_count: 20
passed_required_gate_count: 20
```

Every gate must also have `passed = true` and
`evidence_valid = true`. The v2.0.0 tag is prohibited until that condition is
observed.
