# APM project status

This is the current progress index. Execution evidence, not this file alone,
supports validation and release claims.

## Completed bounded preflight

**The authorized APM v5 preflight is complete. Full v5 implementation and release
remain unauthorized; Hart N/P beta normalization remains UNRESOLVED.**

Source: current `main` at `52256141738e2ae34766e7d8e429d2ea6009ee31` plus the
hash-bound exploratory-tool changes recorded in
[`v5_preflight_findings.json`](validation/evidence/v5_preflight_findings.json).
The clean starting checkout was already synchronized with `origin/main`; no reset,
history rewrite or unrelated local change was involved. Package identity remains
`4.0.0+main`.

| Experiment | N | P | Tested boundary |
| --- | --- | --- | --- |
| Hierarchical instance application | PASSED | PASSED | Raw DELVTO/MULU0 and W/L read back; independent untouched twin unchanged. |
| Bad-path and reset controls | PASSED | PASSED | Missing-leaf diagnostics and nominal curves; successful nonzero readback before reset and its loss afterward. |
| Maximum-gm extraction | PASSED | PASSED | Single interior peak at every nominal 5/2/1 mV grid; no extraction substitution. |
| Two-observable mapping | PASSED | PASSED | Four artificial ±10 mV/±2% combinations per point, independently remeasured at 0.5 mV. |
| Measured beta normalization | UNRESOLVED | UNRESOLVED | The retrieved thesis repeats the table/plot conflict; no coefficient adopted or rescaled. |

The mandatory W=1 µm, L=0.12 µm point passed before expansion. All nine combinations
of W=1/2/4 µm and L=0.12/0.24/0.40 µm then passed independently for N/P at 300 K,
`|VDS|=50 mV`, with a 0–1 V control-magnitude sweep. Across the 18 cases, worst
Vth grid spread is 0.06254 µV and beta relative spread is `4.112e-7`. Scaled
Jacobian condition numbers span 4.156–4.854. All 72 artificial targets passed;
worst fine-grid component errors are 1.262 nV Vth and `9.199e-9` relative beta.
Every untouched-twin current curve is identical to its nominal curve.

The final numerical runs used 2,231 fresh ngspice processes, including 36 negative
controls. The original/intermediate minimum runs used another 755 processes.
The first parallel expansion was interrupted after 26 attempted processes: this
host's system `spinit` selects eight threads, and ngspice overrides
`OMP_NUM_THREADS`. Those incomplete runs are retained as NOT_RUN geometry
qualifications, with missing in-flight output identified. Explicit
`set num_threads=1` repaired the contention; all nine points were rerun without
changing bounds, tolerances, observables or models. Raw files and hash inventories
remain under ignored `.apm/v5-preflight/`.

The [source audit](validation/evidence/v5_preflight_source_audit.md) inspected the
original paper, the complete 2022 thesis and the later primary companion paper.
The thesis identifies the original data as STMicroelectronics LVT and later data
as a distinct TSMC standard-Vt process. The latter cannot silently correct the
former. Source uncertainty did not enter or block the artificial experiments.
No author contact or external messaging occurred.

## Checks executed on 2026-09-05

- Original separate preflight suite: 34 passed; repaired suite: 39 passed, no skips.
- Final repository Pytest: 119 passed, no skips. The first run had 118 passed and
  one skipped real-ngspice test; that was not a full-suite pass. A project-local
  ignored symlink to the verified existing ngspice 47 enabled the required rerun.
- Ruff, REUSE, provenance and unflagged `apm validate`: PASSED. Final validation
  also passed its isolated v3 regression (92 tests) and Spectre structural checks;
  this is no real-Spectre or release qualification.
- `apm doctor`: all four native/OSDI runtime smokes PASSED. The Python environment
  was absent in this checkout and was created using `tools/setup-python.sh`.
  Existing `/usr/local/bin/ngspice` and OpenVAF binaries were reused.
- Exact OpenVAF source-pin check: FAILED. Installed source is
  `6a93e9500c07830d1e8a19abdeda8f447f935556`, not pinned
  `fdf2522b70f42793f64b1c72f0195c96dea0cc19`. Its binary matches the existing local
  source build. Doctor's generated model-build metadata hard-codes the repository
  pin; that label must not be treated as actual provenance. No compiler was rebuilt
  and no `src/apm/` change was made. Native-BSIM4 VTG results do not use OpenVAF.
- Frozen v4 byte/mode/inventory audit: 52/52 matched the authority commit. Protected
  models, wrappers, manifests, runtime, variation and version metadata are unchanged.
  All local released tags are unchanged and match authoritative remote refs.

Exact report/log hashes and the validation worktree snapshot
`e14ef167225f893dcb1a0d54d95a3db815265fe33d6468c1be55960bd5de0fbc` are recorded
in the findings. These checks preceded authoring the result-only findings and this
status update; the executed code, tests, source audit and task/tool documentation
were already present. Earlier preparation and interrupted/skipped attempts remain
separately identified, not promoted to current passes.

## Smallest justified next contract

A separately authorized v5 goal could introduce only an optional VTG N/P local
research-variation path: a versioned MG coordinate, explicit geometry/bias domain,
full per-polarity two-observable mapping with cross terms, finite differencing,
conditioning/residual checks, and fresh-process hierarchical readback. Preserve
Benchmark v2, native variation and released electrical/noise semantics.

Measured statistics need a separate source gate covering units, pair/individual
normalization, process identity, geometry/extraction transfer, uncertainty and an
independent current-mismatch check. Keep Hart beta blocked. Only after source
approval should a small circuit/sample-count and tail qualification be specified;
the artificial targets establish no ±6σ support. IO transfer and missing statistical
modes remain separate decisions. Exact compiler provenance also needs repair before
claiming the full pinned reference environment. None of this proposal activates full
implementation or release work.

## Preserved release baseline

APM v1.0.0 through v4.0.0 remain released and immutable.

- v4.0.0 annotated tag object: `797cdf9462db9dd634bff558802bcadaaeb70015`.
- Tagged commit: `d224f279921c7e1ae637fd867e00d450067766c6`.
- Frozen post-tag evidence authority: `02959d4a095062873fa2a3a53936af3cb4598ee3`.
- Historical candidate qualification: 15/15; exact-tag qualification: 16/16.
- Historical reports: `validation/evidence/v4_release_candidate.json` and
  `validation/evidence/v4_post_release_requalification.json`.
- Current APM045 positioning: generic 40/45 nm-class; technical namespace 45nm.
- Models, wrappers, Benchmark v2, native variation, frozen v4 records, and version
  metadata are outside this preflight change and must remain unchanged.

## Historical post-v4 maintenance review

At `b09d104759296e6dd59c6f08e6cd30fa716d6461`, the previous status recorded
119 pytest passes, Ruff and REUSE passes, real ngspice-47 doctor success, provenance
success, unflagged maintenance validation success, and 52/52 frozen artifact matches.
That was validation of the recorded pre-commit working-tree snapshot described in
that commit, not a new run performed for this handoff.

The complete previous development/release narrative remains in Git at
`b09d104759296e6dd59c6f08e6cd30fa716d6461:STATUS.md` and in the frozen v4 evidence.
This current index does not rewrite those records or promote their results to a new
v5 claim. Repository preparation does not claim completion of APM v5.0.0.
