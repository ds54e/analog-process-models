<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# APM v6.0.0 repository redesign

Status: user-authorized implementation specification for the next APM mission.

Reviewed baseline when this specification was written:
`4cd57d98a54ad1cfe8deedf38de39a0b81a22d52` on `main`.

This document supersedes the earlier proposed v5.1 documentation-only plan for the
next implementation task. It does not itself claim that v6 is implemented, qualified,
tagged, or released.

The autonomous implementation stop is **V6_RELEASE_READY** at one exact candidate
commit/tree. Creating an annotated `v6.0.0` tag and publishing a GitHub Release require
a later explicit user approval.

## 1. Mission

Redesign APM so that three concerns are cleanly separated:

1. **current use** — models, characterization, noise and supported variation flows;
2. **current development and validation** — the code and checks needed for the live
   version; and
3. **historical release reproduction** — immutable tags, release evidence and dated
   release procedures.

At the same time, complete the user-facing documentation cleanup that had been
planned for v5.1.

The result should be an understandable and maintainable analog research toolkit, not
just a shorter README. A new user should be able to choose a model, run a documented
example, find the resulting data and understand its scientific limits. A maintainer or
agent should be able to identify the active instructions without importing or treating
old release implementations as current code paths.

This is a repository, validation and usability redesign. **Preserve what APM v5 means
scientifically.** Do not invent a physics/statistics feature merely to justify a major
version.

## 2. Starting authorities and preservation requirements

Before editing anything, synchronize safely with current authoritative `main` and
record the actual starting commit/tree. Review intervening commits if `main` has moved.
Never reset, force-push, rewrite published history or discard unrelated newer work.

The following released identities were known at preparation time and must be verified
from Git before implementation rather than blindly trusted from this document:

- released `v5.0.0` annotated tag object:
  `b1a4246b9189fe33915d457e9d7f2938869b8fdf`;
- released `v5.0.0` commit:
  `381517fda5107fabf98af7801d5a5103f38e230c`;
- frozen v5 evidence authority:
  `150084368815f6a57eae9f3e707f685149e920d3`;
- frozen v4 authority:
  `02959d4a095062873fa2a3a53936af3cb4598ee3`;
- completed v5 preflight authority:
  `bbb585306f13614b7649c36dd5b7510c845daed9`.

Preserve every released tag and Git object. Do not move/recreate a release tag. Do not
amend tagged commits.

Before structural migration, read at least:

- `AGENTS.md`;
- `GOAL.md`;
- `STATUS.md`;
- `README.md`;
- `ENVIRONMENT.md`;
- `CONTRIBUTING.md`;
- `APM045_POSITIONING.md`;
- `DEVICE_FAMILY_MODEL.md`;
- `RESULT_CONTRACT.md`;
- `NOISE_CHARACTERIZATION.md`;
- `V5_RESEARCH_VARIATION.md`;
- `validation/release_gates_v5.toml`;
- `variation/research/apm045/sources.toml`;
- `src/apm/maintenance_validate.py` and its tests;
- current project-root/toolchain/CLI routing;
- the historical release validators and frozen path selectors that current code still
  imports or depends on.

The current `GOAL.md` still describes post-v5 maintenance. The user has now authorized
this v6 mission. The first implementation step is to migrate mutable GOAL/current
lifecycle checks coherently; do not leave a new mission paired with obsolete tests.

## 3. Scientific and compatibility boundary

Default rule: v6 changes repository architecture and usability, **not scientific
meaning**.

Preserve unless a concrete defect is independently demonstrated and reported:

- all nominal model cards, wrappers and manifests;
- the five-technology / fifteen-family / thirty-public-MOS catalog semantics;
- Technology -> Electrical Family -> Device;
- Operating Profile, Backend Binding, Variation and Comparison Set separation;
- planar `w,l` and FinFET `l,nfin` public geometry;
- terminal order and signed/raw versus positive-magnitude result semantics;
- canonical terminal finite-difference gm/gds;
- full complex terminal-Y/capacitance semantics;
- released stationary-noise acquisition/fit/result semantics;
- Benchmark v2 distributions and meaning;
- APM130 native variation semantics;
- v5 Research Local schemas, extraction method, profile meaning, RNG identity,
  mapping behavior and replay semantics;
- the required OpenVAF source pin and observed-provenance rules;
- ngspice 47 as the reference real simulator;
- Spectre as model-only experimental/unverified.

Research Local remains the released APM045 VTG N/P local Vth/current-factor model in
its qualified geometry/reference domain. Original Hart/ST40 beta remains
`BLOCKED_NORMALIZATION_CONFLICT`. The independent Hart/TSMC40 companion remains a
source-transfer hypothesis, not a correction, foundry correlation, yield model or
reliability model. IO18/IO25 Research transfer remains unresolved with no default
numeric mismatch profile. Unknown beta is not zero.

Do not add Research Global/All, new IO statistics, passive mismatch, layout/spatial
variation, noise Monte Carlo, RTN/aging, yield/reliability, new nominal device
families, real Spectre/Virtuoso claims, optimization/autonomous research campaigns,
or Analog Design Model Lab functionality in this mission.

Preserve existing public scientific CLI command/option behavior unless a compatibility
shim is genuinely required by the repository migration. Do not rename model public
names or result fields for cosmetic cleanup.

If a true scientific/runtime defect is found, keep a minimal reproducer, complete all
independent migration work, and report the defect. Do not hide a scientific change in
the architectural cleanup.

## 4. Core architectural redesign

### 4.1 Current runtime must not depend on old release implementations

Trace imports and file lookups, then remove accidental dependencies such as current
root detection or ordinary validation relying on historical release contracts only
because they happen to be present.

The desired dependency direction is:

```text
current runtime/helpers
        ^
        |
current validation/release lifecycle

historical release reproduction  -->  exact historical Git source/evidence
```

Historical validators must not be foundational libraries for the current runtime.
If a historical module contains logic still needed today, extract or reimplement the
small reusable helper in a current neutral module, add old/new equivalence tests, and
leave the historical source itself immutable.

Avoid a broad framework rewrite. Prefer small explicit modules over plugin systems,
registries or generic workflow engines.

### 4.2 Project discovery must describe the current project

Current source-tree discovery should use a stable current project marker, not the
presence of a v3 release-gate filename as the defining identity of APM.

Design one simple current root identity and test it from:

- repository checkout root;
- nested working directory;
- editable installation;
- explicit `APM_REPO_ROOT`;
- a source snapshot containing current runtime assets but not full historical Git
  history.

Historical audit operations may require Git history. Ordinary model use and current
runtime should not silently require all historical Git objects.

### 4.3 Separate current validation from historical release reproduction

Create a clean current validation layer for v6. It should validate current package,
models, manifests, provenance, docs and compatibility without pretending that old
release validators are current validators.

Historical validation must remain reproducible from exact historical refs. It may be
invoked through explicit archive/reproduction tooling or documentation, but ordinary
`apm validate` must not run an ever-growing chain of old release implementations as
its architecture.

Do not edit frozen v3/v4/v5 validators to make them accept v6 source.

### 4.4 Separate release preservation from live-tree duplication

The long-term authority for a past release is Git: annotated tag -> tagged commit/tree,
plus any explicitly recorded post-tag evidence authority.

Migrate selected historical working-tree copies only after proving that:

1. the exact original object/inventory/mode can be located from the declared authority;
2. all current runtime references to that path have been classified;
3. current-runtime-required assets remain locally available under a stable current
   contract;
4. historical material can be reconstructed/exported from the repository history; and
5. negative tests reject wrong/missing tags, commits, authorities or incomplete history.

Do not equate "stored in Git history" with "safe to remove" until dependencies are
traced. Some files that look like evidence are runtime inputs. For example, the v5
research profile currently verifies a source-decision hash. Keep runtime-required
source decisions/datasets/credit/license data available and protected; do not break the
approved profile merely to make directories prettier.

Do not rewrite history. Historical cleanup must be normal forward commits.

### 4.5 Historical reconstruction/export

Provide one explicit tested way for a maintainer to inspect/export a historical
release and its evidence. The exact mechanism may use normal Git objects/archives and,
where useful, a Git bundle for offline reconstruction.

Test the reconstruction in a separate temporary repository. Verify refs and object
identity after reconstruction. Do not claim that ignored `.apm` raw simulator runs or
external compiler binaries are preserved by a Git bundle when they are not committed.
State the boundary between committed evidence, hash references and external/raw state.

Shallow/incomplete clones must fail historical-integrity checks honestly and explain
what is missing; they must never be counted as a historical PASS merely because current
runtime commands work.

## 5. Documentation redesign

Complete the v5.1 usability plan as part of v6.

### 5.1 Project positioning

Use a present-tense task-oriented description. Recommended short description:

> Open compact models and ngspice tools for analog device, noise, and mismatch studies.

Recommended README opening direction:

> Analog Process Models (APM) provides MOS compact models and ngspice-based tools
> for analog circuit research. Use the models in your own circuits, characterize
> devices, compare electrical families and technology classes, and study stationary
> noise and supported variation models.
>
> The collection combines redistributed open models with APM-authored generic
> models. It is a research toolkit, not a manufacturable PDK. Model provenance,
> supported ranges, and the limitations of each type of study are documented.

Refine wording only against implemented capabilities. Do not market a future AI or
autonomous analog-design platform as a current feature.

README should be an entry page, not a release-validation narrative. Avoid candidate
SHAs, gate counts, build receipts and development anecdotes in its introduction. Keep
exact release/evidence links available under clearly labeled maintainer/history paths.

### 5.2 Required user-facing information architecture

Use existing guides where suitable, but provide these roles:

- `README.md` — what APM is, core tasks, model overview, entry commands, boundaries;
- `docs/index.md` — task-based navigation, technical references, maintainer/history
  entry;
- `docs/getting-started.md` — prerequisites, cold setup, verified warm reuse, first
  result, setup failures;
- `docs/using-models.md` — choose a family and use the actual wrappers in a user SPICE
  circuit; native versus OSDI requirements;
- `docs/noise.md` — run one device-noise example, find outputs, understand units and
  missing-fit states;
- `docs/variation.md` — choose Benchmark, APM130 native or VTG Research Local;
- `docs/characterization.md` — first useful result, outputs and comparisons;
- `docs/research-local.md` — user-oriented sample/run/replay tutorial first, scientific
  identity/reference details later;
- `docs/spectre.md` — preserve experimental/unverified boundary;
- `ENVIRONMENT.md` — current environment/reuse first, historical release details by
  reference rather than dominating the page;
- `CONTRIBUTING.md` — current development and validation entry;
- `GOAL.md` — current authorized v6 work/lifecycle only;
- `STATUS.md` — short dated current snapshot rather than a development diary.

Keep public documentation in English. Do not build a documentation-site framework in
this mission. Avoid creating one page for every subsection.

A primary task should have a useful destination within two links from README.

### 5.3 User journeys that must be tested

J1 First-time visitor: README answers what APM is, whether models can be used directly,
which model origins exist, which simulator is really validated, and whether it is a
PDK.

J2 First execution: from a fresh checkout on the reference platform, follow documented
setup and produce one bounded characterization. Show actual output locations and where
the first useful metrics live.

J3 Returning user: reuse a valid project-local toolchain instead of blindly rebuilding;
reconcile the editable Python installation/version and run current checks.

J4 Use a model in a circuit: provide a minimal runnable nominal SPICE example using
actual wrapper/model names and terminal/geometry conventions. Explain OSDI-backed
families separately.

J5 Noise: run one real device example; identify terminal drain-current PSD and
input-referred voltage PSD units/files and explicit missing-fit states. Do not imply
silicon-calibrated noise, transient noise or oscillator phase noise.

J6 Variation selection: provide a compact comparison of Benchmark, native APM130 and
Research Local. Do not advertise one generic "Monte Carlo supported" flag.

J7 Saved realization/replay: sample once, run, replay the same realization at another
condition, and explain that a new sample index is a different physical draw. Preserve
existing supported input/path semantics; do not weaken hashes for portability.

J8 Failure/unsupported request: include tested examples for at least an existing output
location, unsupported Research family and malformed/tampered saved record. Recovery
must not silently replace a seed/draw or bypass integrity checks.

J9 Maintainer/agent: current instructions are obvious; historical release procedures
are never presented as ordinary user setup.

Execute allowlisted published tutorial commands themselves. Do not keep a private
working command while publishing a different untested command.

## 6. Version and compatibility policy

Development identity: `6.0.0.dev0`.
Frozen candidate identity: `6.0.0`.
After a future successful publication, mutable main may use `6.0.0+main`.

Because this mission intentionally changes documented maintainer/release workflow and
historical repository organization, document the v6 migration boundary explicitly.
Do not manufacture scientific incompatibility to justify the version.

Where old public scientific runtime commands/result schemas are preserved, add tests
that prove their behavior remains compatible.

If historical release CLI flags are removed or changed on current v6 `main`, provide a
clear diagnostic that directs users to the exact historical tag/procedure rather than
silently running current code with old semantics.

## 7. Validation design

Create a machine-readable v6 gate contract and a fail-closed candidate evaluator.
Design the post-tag phase before freezing the candidate so v6 does not repeat the v5
late exact-tag-tooling problem.

At minimum, candidate gates must cover:

1. `preservation.release_history`
   - exact existing tags/objects/authorities;
   - migration inventories complete;
   - no released object rewritten.
2. `preservation.current_science`
   - nominal model/profile/source/method inputs required for current behavior exact or
     explicitly proven equivalent;
   - no accidental scientific diff.
3. `architecture.current_dependency_graph`
   - ordinary runtime/current validation no longer foundationally imports old release
     validators or depends on incidental historical paths.
4. `architecture.history_reconstruction`
   - historical export/reconstruction tested in a separate repository;
   - wrong/incomplete history rejected.
5. `identity.lifecycle`
   - project/runtime/installed/CLI identities agree and source phase is explicit.
6. `quality.current`
   - complete current pytest, Ruff, REUSE, provenance, security/distribution checks;
   - no hidden required skip.
7. `docs.navigation_claims`
   - links/anchors/current catalog/CLI claims checked; model/source/licensing boundaries
     reviewed.
8. `examples.real_execution`
   - published nominal/model-use, characterization, noise, variation, replay and
     negative examples execute on the reference tools with evidence.
9. `compatibility.electrical`
   - current electrical characterization/comparison behavior rerun and compared to
     declared compatible baseline.
10. `compatibility.variation`
    - Benchmark and APM130 native behavior rerun and compared.
11. `compatibility.noise`
    - existing stationary-noise method/catalog coverage appropriate to v6 rerun and
      checked without changing released semantics.
12. `compatibility.research_local`
    - run the frozen v5 research confirmation plan or an explicitly equivalent v6
      compatibility campaign using unchanged scientific inputs; preserve draw/raw
      realization identity and report old/new differences.
13. `validation.negative_controls`
    - deliberate broken history, protected/current input drift, stale evidence,
      corrupted record/cache, unsupported family and wrong lifecycle are rejected.
14. `environment.reproducibility`
    - both cold project-local bootstrap and fresh-source/fresh-venv warm reuse of a
      verified read-only toolchain are distinguished and checked.
15. `release.clean_candidate`
    - exact clean source commit/tree, independent fresh clone, hash-bound evidence,
      clean before/after.

Add one separate post-tag `release.exact_tag_requalification` gate. It must verify the
annotated tag object/peeled commit and rerun the complete required v6 candidate suite
from a genuinely fresh detached checkout before publication could be authorized.

The exact gate inventory may be refined during implementation, but it must not be
weakened after observing failures. Freeze the contract, compatibility matrices, seeds,
selected tolerances and tutorial command inventory before the final candidate run.

## 8. Old/new scientific compatibility

Because v6 changes routing and validation structure, allocate substantial effort to
proving that science did not move.

For representative/current required flows, execute the v5 baseline and v6 candidate
with matched inputs and the same verified real tools. Compare scientific outputs,
statuses and identities. Exclude only explicitly enumerated nondeterministic metadata
such as timestamps or clone-local absolute paths when scientifically irrelevant.

Do not compare only exit codes. Check the actual numerical/output contracts.

For Research Local specifically:

- preserve source/profile hashes and coefficient meaning;
- preserve the normal draws for identical seed/index/UID;
- preserve resolved raw DELVTO/ln(MULU0) values when the same mapping inputs apply;
- replay representative v5 saved realizations under the unchanged supported binding
  context;
- rerun the required v5 statistical/circuit qualification on v6 if current routing or
  helper extraction touched that execution path;
- never edit v5 evidence to call a v6 result a v5 pass.

If a compatibility discrepancy is discovered, classify it before acting:

- expected metadata/routing migration;
- pre-existing bug revealed by the new checks;
- unintended v6 regression;
- genuine scientific change requiring new authorization.

## 9. Historical migration safety

Before removing/moving any historical live-tree file, generate a dependency and
migration manifest including:

- current path;
- classification: runtime input / current reference / historical task record /
  historical evidence / release implementation;
- authoritative tag/commit/evidence authority;
- byte hash and mode;
- current import/read/link references;
- planned v6 disposition;
- reconstruction command/test.

Do not use filename patterns alone to infer safety.

The v5 frozen selector currently includes broad areas such as `validation/evidence`
for `v5_*`, research source/profile material, v5 tools/validators and release
procedures. Do not create new v6 evidence inside an old frozen namespace, and do not
weaken old selectors merely to permit migration. Build a new v6 preservation contract.

Historical evidence that is still a current runtime input remains in the current
runtime set even if a copy also exists in history.

## 10. Implementation sequence

A. **Baseline / dependency trace**

- synchronize main;
- record tag/authority identities;
- inventory frozen/current/history paths;
- trace current imports/file reads/links;
- define the new current project marker and v6 gate/migration plan;
- migrate GOAL/current lifecycle tests to the authorized mission.

B. **Current architecture separation**

- extract current reusable validation helpers from historical modules where needed;
- remove ordinary runtime/current-validator dependency on old release implementations;
- redesign root/project discovery;
- add negative/equivalence tests;
- keep scientific runtime changes minimal.

C. **Documentation/user experience**

- rewrite README and STATUS;
- add/repair task navigation and guides;
- move qualification details out of user quick starts;
- execute and refine published user journeys using actual outputs.

D. **Historical preservation migration**

- build the migration manifest;
- retain runtime-required assets;
- move/remove selected historical live-tree copies only after reconstruction proof;
- add historical export/reconstruction tooling and incomplete-history negative tests;
- keep every released tag/object untouched.

E. **Compatibility and validation**

- run current static/unit/provenance/licensing checks;
- run real electrical, variation, noise and Research Local compatibility suites;
- execute cold setup and verified warm-reuse paths;
- run tutorial negative controls;
- retain failures and fix only in-scope causes.

F. **Candidate qualification**

- freeze code/docs/migration manifest/gates/tests at `6.0.0`;
- create one exact clean candidate commit and push via normal fast-forward history;
- create a genuinely independent fresh clone of that exact commit;
- run all required candidate gates;
- commit only compact result references afterward if needed, clearly pointing back to
  the tested candidate;
- stop at `V6_RELEASE_READY`.

Do not stop after the architecture or documentation phase and call the mission done.

## 11. Git and execution rules

- Work on current `main` using normal fast-forward history.
- Preserve unrelated work.
- Commit coherent progress; do not leave one enormous unreviewable final commit.
- Never force-push.
- Never move/recreate/delete a released tag.
- Keep generated toolchains, venvs, raw simulation runs, temporary bundles and large
  comparison artifacts ignored.
- Commit compact, hash-linked evidence and migration manifests.
- Do not make external author contacts or buy data.
- Do not change repository visibility, owner, default branch or security settings.
- GitHub About text may be prepared, but external metadata changes are separate from
  the repository mission unless explicitly authorized and supported.

## 12. Stop states and final report

Successful autonomous stop:

`V6_RELEASE_READY`

with exact candidate commit/tree and all candidate-required gates passing.

No `v6.0.0` tag or GitHub Release is authorized by this specification.

For a genuine blocker, finish all independent work and report the exact blocker with
retained evidence. Never convert missing, skipped, stale, unknown, unavailable or
failed evidence into PASS. Never reduce the scientific/compatibility scope after a
failure merely to finish overnight.

The final Codex report must include:

- actual implementation baseline;
- exact tested v6 candidate commit/tree;
- coherent commit sequence pushed to main;
- final repository/documentation structure;
- historical migration manifest summary and reconstruction test;
- old/new compatibility results for electrical, variation, noise and Research Local;
- cold setup and warm-reuse results;
- executed tutorial journeys and failure controls;
- full candidate gate inventory/results/evidence paths;
- known remaining limitations or blockers;
- explicit statement that no `v6.0.0` tag or GitHub Release was created.
