# APM project status

This is the current progress index. Execution evidence, not this file alone,
supports validation and release claims.

## Current task

**APM v5.0.0 preflight: instructions and exploratory tools prepared in the repository.**
Read `GOAL.md`, `V5_PREFLIGHT.md`, and `tools/v5_preflight/README.md`.
The English launch prompt is `tools/v5_preflight/CODEX_PROMPT.md`.

- Current line: post-v4 maintenance with explicitly authorized bounded preflight.
- Package identity: `4.0.0+main`, unchanged.
- Full v5 implementation/release: not yet authorized by this preflight task.
- Preparation environment: non-reference Python environment, no ngspice binary.
- Real ngspice instance-application/extraction/mapping experiments: NOT_RUN during
  repository preparation; run these on the existing WSL2/EL9 ngspice 47 host.
- Hart beta coefficient: normalization UNRESOLVED; no approved runtime value.
- Current full repository validation: NOT_RUN during preparation. Earlier post-v4
  PASS results below are historical and do not validate this newly prepared tree.

The preparation snapshot and exact tool-file hashes are in
`validation/evidence/v5_preflight_preparation.json`. Imported prototype tests use
artificial quantities; their success is not statistical-profile or release evidence.

## Next actions for Codex

Review the experimental scaffold, locate/reuse the existing reference environment,
rerun the preflight tests, and execute the three minimum experiments independently
for VTG N/P. Investigate the beta source issue in parallel. Write new concise results
at `validation/evidence/v5_preflight_findings.json` and
`validation/evidence/v5_preflight_source_audit.md`, retaining all negative findings.
Then update this index from the checks actually run and propose the next full-v5
contract. Do not create a tag, release, or production variation feature in this task.

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
  metadata are outside this instruction-import change and must remain unchanged.

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
