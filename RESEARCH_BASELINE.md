# Upstream Research Baseline

This file records externally researched facts that informed the initial APM specification. It is a **dated implementation aid**, not immutable policy. Upstream projects can change; re-check authoritative sources before pinning or vendoring anything.

Baseline date: **2026-08-29**

If this file conflicts with `AGENTS.md` or `GOAL.md`, follow the normative repository contract. If current authoritative upstream evidence differs from this baseline, use the current evidence and record the material change in `STATUS.md` and provenance metadata.

## ngspice

Authoritative sources:

- https://ngspice.sourceforge.io/download.html
- https://ngspice.sourceforge.io/docs.html

Baseline findings:

- ngspice **47** is the current stable release as of this baseline date.
- The upstream download page describes ngspice 47 as the stable end-user release.
- Upstream does not provide a normal precompiled Linux stable package; Linux users may use distro packages or compile the release from source.
- The v1.0 APM target is ngspice 47 with OSDI support.
- OSDI capability must be proven by a real loaded compact-model simulation, not inferred from version text alone.

Implementation implication:

On the reported bare AlmaLinux environment, source-building ngspice 47 is an expected M0 path if the available package is absent, stale, or lacks the required OSDI configuration.

## OpenVAF-ReLoaded

Authoritative upstream:

- https://github.com/OpenVAF/OpenVAF-Reloaded

Baseline findings from the upstream README:

- OpenVAF-ReLoaded generates OSDI model libraries.
- Current development uses OSDI API **0.4**.
- The legacy `osdi_0.3` branch is no longer maintained.
- The upstream compatibility table states ngspice >=44 supports OSDI 0.3 and 0.4 (using the relevant compatible subset).
- 64-bit Linux binaries are available upstream.
- Source builds support LLVM 18 through 21 at this baseline and require an explicitly selected/detected LLVM version plus Rust tooling.
- Upstream project license is GPL-3.0; OpenVAF-ReLoaded is an external build tool and is not intended to be vendored as APM project code.

Implementation implication:

Pin the actual OpenVAF-ReLoaded revision/binary used for v1.0 validation and prove compatibility with the selected ngspice 47 build by compiling/loading the real PSP103 and BSIM-CMG paths.

Do not assume Verilog-A RNG support is available or suitable for APM benchmark Monte Carlo; the benchmark reference flow remains Python-generated resolved samples plus deterministic ngspice runs.

## BSIM-CMG

Authoritative source:

- https://bsim.berkeley.edu/models/bsimcmg/

Baseline finding:

- Latest standard BSIM-CMG version is **112.1.0**, dated **2026-04-28**.

Implementation implication:

112.1.0 is the preferred initial engine revision to investigate/pin for APM016F, subject to:

- obtaining the exact authoritative distributable source;
- auditing the exact source/license/agreement text being shipped;
- confirming OpenVAF-ReLoaded compilation;
- confirming ngspice 47 OSDI execution;
- keeping the APM016F **parameter deck** independently APM-authored.

Do not substitute a PTM-MG parameter deck merely because it already runs.

## IHP SG13G2 / PSP

Authoritative upstream:

- https://github.com/IHP-GmbH/IHP-Open-PDK

Relevant baseline file:

- `ihp-sg13g2/libs.tech/ngspice/models/sg13g2_moslv_mod_mismatch.lib`

Baseline findings:

- IHP SG13G2 is a 0.13 um BiCMOS open PDK with low-voltage MOS device models suitable as APM130's foundry-derived open anchor.
- The open PDK README currently describes the open-source PDK content as **Preview**, even though the underlying SG13G2 process/PDK lineage has manufactured designs. APM must therefore avoid upgrading that into an independent production/silicon-correlation claim.
- The inspected low-voltage MOS mismatch file identifies the model as **PSP 103.6**.
- That file carries an Apache-2.0 header.
- The mismatch wrapper visibly uses local randomized quantities including `delvto` and `factuo`, with geometry/multiplicity-dependent scaling in the upstream native model.

Implementation implication:

- Treat **PSP103.6** as the concrete initial APM130 compact-model target, while recording the exact IHP revision actually vendored.
- Preserve IHP-native variation semantics separately from APM benchmark variation.
- Do not copy IHP's native multiplicity/mismatch semantics into the APM common public geometry contract.
- Do not invent a native Process+Mismatch "All" mode unless the selected upstream model explicitly provides and validates one; APM Benchmark Variation has its own required `all` mode.

## FreePDK45

APM currently intends to use a minimal, clearly redistributable FreePDK45 simulation-model subset as APM045.

A clean/open mirror has been considered during project definition, but **the exact imported files, exact revision, and file-level redistribution terms must still be audited during implementation**.

Do not treat this research baseline as license authorization. `models/apm045/provenance.toml`, `THIRD_PARTY.md`, and the exact upstream file headers control the eventual vendoring decision.

## APM350 candidate

A generic SCN4M_SUBM-class open model is the current APM350 candidate, with the `silicon-vlsi-org/eda-technology` repository considered during project definition.

The intended metadata distinction is:

- technology class: 0.35 um-class;
- actual model Lmin: whatever the selected model explicitly supports, potentially around 0.4 um.

The exact model file's provenance/header/license must be re-audited before vendoring. If redistribution remains ambiguous, use another clearly redistributable source or author an APM generic BSIM3 deck rather than blocking the release.

## Spectre

The project-definition research found the required compact-model families conceptually available in modern Spectre flows (BSIM3, PSP, BSIM4, BSIM-CMG) and normal Spectre Monte Carlo modeling uses `statistics` process/mismatch semantics.

However, APM's local v1.0 development environment does not include validated Spectre execution. Therefore this research is only a design basis for the **experimental/unverified model-only compatibility layer**.

Do not turn internet documentation into a claim that APM Spectre model files parse or simulate correctly. Real Spectre conformance is deferred until an actual Spectre environment is available.

## Research discipline for the implementation agent

When a baseline fact matters to a release claim:

1. re-check the authoritative upstream source;
2. pin the exact version/revision used;
3. prefer primary project documentation/source over search snippets or third-party summaries;
4. record the result in provenance/evidence;
5. distinguish an upstream statement from something APM actually validated locally.
