# APM v2.0.0 release-readiness evidence

Gate / milestone: V2-M8 public-claim/provenance integration and V2-M9 release
candidate preparation

Status: validated candidate; final evidence-bound commit requalification
pending before tag

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
- `validation/evidence/v2_provenance.json`; and
- `validation/evidence/v2_release_candidate.json`.

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

## Exact-commit candidate result

An untouched GitHub clone of commit
`7a83620f2504539f5bf0c1e4637594d3b0232e94` was attested before bootstrap on
WSL2 + AlmaLinux 9.7 x86_64 on ext4. The documented bootstrap rebuilt ngspice
47, OpenVAF-Re-Loaded, PSP103/PSP103-NQS OSDI, and BSIM-CMG OSDI. The complete
release command ran from 2026-08-30T02:14:39Z through 02:18:39Z and reported:

```text
schema: apm.release-validation.v2
target: v2.0.0
status: pass
required_gate_count: 20
passed_required_gate_count: 20
every required gate passed: true
every required gate evidence valid: true
report sha256: 76f643882c67bbe937a5ccfbd2c57b403de49ed78d1f4ad1fe63fa9a0682f32b
```

The exact component report hashes and ordered gate IDs are retained in
`validation/evidence/v2_release_candidate.json`.

## Final tag condition

Committing this evidence changes `HEAD`, so the candidate result does not by
itself authorize a tag on the successor commit. The authoritative final
evidence must come from another untouched, attested WSL2 + RHEL-compatible EL9
x86_64 clone at the exact evidence-bound commit after documented bootstrap.
The final `apm validate --release --output .apm/results/v2-release` report
must again show:

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
