# APM v6.0.0 implementation handoff

Status: implementation plan, not implementation or qualification evidence.
Prepared on 2026-09-05 from the repository and the earlier v5.1 design handoff.
When supplied as the selected Codex task, this document supersedes that v5.1
proposal. Do not implement or release an intermediate v5.1 merely to follow the
previous discussion. The autonomous finish is `V6_RELEASE_READY` at an exact
candidate commit. Creating a tag or publishing a release requires separate approval.

## 1. Mission and scope

Make APM a coherent, maintainable research toolkit by separating current use,
current development, and historical release reproduction. Complete the user-facing
work planned for v5.1 and remove the structural dependencies that would make that
cleanup temporary.

This is a repository, validation, and usability redesign, not a new device-physics
or statistical-modeling program. Preserve what APM v5 scientifically means.
There is no requirement to invent a scientific feature to justify a major version.
The deliberate migration of documented maintainer workflows and historical file
locations is the version boundary; document it explicitly.

Required outcomes:

1. A concise project introduction and executable, task-oriented English guides.
2. Current runtime, project discovery, and current validation no longer depend on
   historical release implementations or incidental historical file locations.
3. A complete, auditable migration from selected live-tree historical copies to
   exact Git-object preservation, with independently checked inventories and a
   tested reconstruction/export path.
4. Continued local availability and integrity checking of all assets needed by
   current simulations, including source decisions that are runtime dependencies.
5. Small, separated validation layers with genuine negative tests and a reusable
   current release lifecycle, rather than another hardcoded chain of old validators.
6. Demonstrated scientific compatibility, clean-source reproducibility, and an
   exact candidate with all v6 required gates executed.

Additional implementation budget should go into dependency tracing, migration
verification, old/new comparisons, and failure tests, not speculative features.
Do not stop at an inventory, proposed architecture, documentation draft, successful
bootstrap, or partially completed verification campaign.

## 2. Reviewed baseline and immutable identities

Repository: `ds54e/analog-process-models`.
Authoritative remote: `https://github.com/ds54e/analog-process-models.git`.

Reviewed main commit: `4cd57d98a54ad1cfe8deedf38de39a0b81a22d52`.
Reviewed main tree: `090837a7f99772c1d07d6c6f61b4df4ffe735898`.

Observed annotated tag objects:

| Release | Tag object |
| --- | --- |
| v1.0.0 | 1633cc3b6d1b45ef4b77d778e95d069aaa03f513 |
| v2.0.0 | 89b9ce70cfa15e92ca6473f1916d50f77c7b95dc |
| v3.0.0 | afecec29ea6ed0703ef441d4839fd40a238bef0b |
| v4.0.0 | 797cdf9462db9dd634bff558802bcadaaeb70015 |
| v5.0.0 | b1a4246b9189fe33915d457e9d7f2938869b8fdf |

Additional known authorities:

- v5 released source: `381517fda5107fabf98af7801d5a5103f38e230c`.
- v5 released tree: `8751c3ed03dc31c87f52d3eb3c5c0b4da903ed65`.
- v5 post-publication evidence authority: `150084368815f6a57eae9f3e707f685149e920d3`.
- v4 released source: `d224f279921c7e1ae637fd867e00d450067766c6`.
- v4 evidence authority: `02959d4a095062873fa2a3a53936af3cb4598ee3`.
- completed preflight authority: `bbb585306f13614b7649c36dd5b7510c845daed9`.

Verify these against the authoritative repository. Discover and record the other
peeled commits, trees, and evidence authorities from their actual records; do not
fill gaps by guessing. A source tag and a later evidence authority are distinct.
For example, the v5 tag predates its final candidate/exact-tag evidence summaries.
Saving only the tagged source would omit some of the evidence being preserved.

Synchronize safely with current main. If it advanced, review intervening commits,
record the actual starting point, and preserve unrelated work. Do not reset to the
reviewed baseline, force-push, amend a published commit, or manufacture a new
baseline that conceals intervening changes.

## 3. Explicit policy transition

Before moving or removing anything, read the current AGENTS, GOAL, STATUS,
maintenance validator, all frozen selectors, release procedures, relevant tests,
licenses, and current source/runtime dependencies.

This selected v6 task authorizes changing *current-main policy and architecture*
so that appropriate historical artifacts need not remain at their old live-tree
paths. It does not authorize changing any historical Git object, tag, release,
authority, evidence statement, model, statistical coefficient, or historical
acceptance criterion. Update mutable AGENTS/GOAL/current checks coherently to
record this distinction and the explicit migration.

The earlier rule requiring selected historical copies in the current working tree
is superseded only through the verified migration described below. It is not
superseded by deleting the old tests, relabeling modified copies as originals,
or replacing every failed check with an exception.

Keep a small, committed v6 plan and acceptance manifest. Prefer a maintainer/spec
location such as `docs/maintainers/v6-plan.md`, linked from GOAL, over another large
root-level mission file. This handoff can supply that plan rather than being copied
into several new contracts. Use a short Codex routing file, not repeated long prompts.

## 4. Scientific and safety invariants

Preserve nominal model bytes, public model names, model/provenance manifests,
public terminals and sizing, source coefficients, approved profile bytes and IDs,
extraction definitions, variation distributions and correlation assumptions,
geometry/support ranges, and result semantics. Preserve the three distinct flows:
Benchmark, APM130 native, and APM045 VTG Research Local.

In particular:

- Technology -> Electrical Family -> Device remains the domain model.
- Operating Profiles are choices, not reliability or fabrication ratings.
- Planar W/L and FinFET L/NFIN remain distinct; no invented common effective width.
- Canonical gm/gds, terminal Y and stationary-noise definitions remain unchanged.
- The nominal five-technology, fifteen-family, thirty-public-MOS catalog remains
  unchanged, verified against manifests rather than only copied prose.
- VTG Research Local remains N/P, W=1-4 um, L=0.12-0.40 um; statistical anchor
  300 K, mapping |VDS|=50 mV and VBS=0. Temperature replay is not calibrated
  temperature-dependent statistics.
- The coherent Hart/TSMC40 companion profile remains a transfer hypothesis.
  Original Hart/ST40 beta remains BLOCKED_NORMALIZATION_CONFLICT for N and P.
- No rescaling/splicing of source coefficients, new covariance, or source refitting.
- IO18/IO25 research transfer remains UNRESOLVED_WITH_EVIDENCE, without a numeric
  default profile or implicit beta=0. Research Global/All remain unsupported.
- Keep source uncertainty, model-construction uncertainty, and device randomness
  separate. No yield, reliability, foundry correlation, or silicon-calibration claim.
- Retain actual observed OpenVAF provenance at required pin
  `fdf2522b70f42793f64b1c72f0195c96dea0cc19`. Do not change the pin to fit a host.
- EL9 x86_64 / ngspice 47 remains the reference. Spectre stays model-only,
  experimental and unverified; no Virtuoso integration claim.

Do not add new nominal families, Research Global, IO statistics, LDO/OTA design
optimization, an agent framework, autonomous discovery campaigns, a general
workflow/database/plugin engine, cloud services, new platform support, or noise-MC.
The downstream LDO/design-research work should be easier to start, not absorbed into
this repository redesign. Do not turn APM's public description into an AI product.

No tag/release creation, release edits, external messages, author contact, paid data,
repository renaming/visibility/security changes, or system-tool replacement is
within this task. Keep legitimate raw runs and binaries ignored and preserve existing
user work, verified toolchains, caches, and evidence. Do not use broad destructive
cleanup of `.apm` as a migration technique.

## 5. Dependency-first migration

Build an exact inventory before implementation. Classify *every* protected or
historical artifact selected for migration and every dependent import/path.
At minimum, distinguish:

A. Current runtime asset: must remain available locally for normal use.
B. Current normative reference: still defines a supported contract.
C. Current maintainer policy/helper: may be rewritten with equivalent checks.
D. Historical release implementation or procedure: belongs to its exact source.
E. Historical evidence: bound to its exact authority, which may follow the tag.

Record old path, role, original commit/tree/blob/mode and SHA-256, inbound runtime,
test/doc/license references, migration action, destination or exact history locator,
and verification. Capture symlink content/modes and executable bits, not only text.
Generate the baseline inventory from the pre-migration Git objects and old audit
selectors, not from an already-reorganized current tree. Cross-check the resulting
old and new audit inventories before switching enforcement.

There are concrete traps in the reviewed code:

- `src/apm/paths.py` recognizes a checkout by the historical
  `validation/release_gates.toml` file.
- `src/apm/maintenance_validate.py` imports functions from historical v3/v4 release
  validators; `src/apm/cli.py` also imports old release paths at module import time.
- `src/apm/research.py::load_profile` reads the registry and hashes a source decision
  currently under `validation/evidence/`. This is not disposable documentation.
- saved research records and caches bind code/input/recipe/model identities. A new
  run ID after a code refactor is not permission to silently rewrite old records.
- old preservation selectors include broad path prefixes, such as `v5_*` evidence.
- historical tests and current tests are interleaved; obsolete version assertions
  must not be confused with still-required scientific/provenance tests.

Tracing must include runtime I/O, generated paths, resource discovery, tests, build
scripts, example input files, local include closure, licensing inventories, and
content hashes. A text search for imports alone is insufficient.

## 6. Preservation design

### 6.1 Separate historical identity from current asset integrity

Maintain two distinct checks:

1. Historical release integrity: the expected annotated tag object, peeled source
   commit/tree, evidence authority, exact historical artifact inventory/bytes/modes,
   and reconstructibility from those Git objects.
2. Current scientific asset integrity: every still-used model/profile/source asset
   has the expected bytes, complete input/notice closure, and compatible semantics
   in the current source tree. Archiving history does not weaken this check.

Do not replace both with 'the old tag exists'. Do not require every old document
and validator to survive in the current tree either.

Use one compact history index, for example `releases/index.toml`, with records for
source and evidence authority, exact identities, artifact inventories/locators,
retained runtime assets, and reproduction notes. Keep release records explicit and
append-only in meaning: a new release may be added, but an old identity cannot
change to match a newly observed value. Validate against the pre-migration anchors.
A self-computed hash is an integrity check, not an independent signature or audit.

### 6.2 Preserve history before removing live copies

For each retirement from main, prove that the original bytes and modes exist in a
reachable immutable source/evidence authority. Verify all necessary references are
reachable from the documented full-clone path, including post-tag authorities.
Prove local reconstruction/export before removing the live copy in a normal new
commit. Do not rewrite history or move tags. Do not keep a second full copy under
`archive/` and call the underlying problem solved.

Provide a small read-only history list/verify/export or prepare operation. Exact
CLI spelling may be finalized once and documented. It must not create or publish
release tags, automatically execute old code, or change the user's checkout.
Use exact pinned objects, not whichever tag happens to resolve today.

A full-clone, offline verification path must work. Also create and verify a
self-contained Git bundle in ignored output and reconstruct a fresh repository
from it as a migration test. Include refs covering the required authority commits;
an incremental bundle with unstated prerequisites is not a self-contained backup.
The bundle is verification output, not a new mandatory runtime dependency and not
an asset to commit into the repository. Exporting a full historical tree preserves
relative links and license context better than disconnected files.

A bundle preserves Git objects, not ignored `.apm` raw runs, Python environments,
compiler binaries, source downloads or unavailable external services. Inventory
those limits separately. Existing hash-only references to host-local raw evidence
must remain honest about availability. Missing old raw logs do not become verified
because the committed summary is intact; newly executed evidence is separate.

### 6.3 Shallow clones and no-Git use

Do not introduce Git history as a dependency of normal simulation. Preserve the
source-tree distribution model; standalone wheel packaging is not required here.
With all current runtime assets and configured tools present, list/describe/model
use/characterization/research must not fetch historical files or papers at runtime.

When a source archive or shallow clone lacks history, historical verification must
report NOT_VERIFIED/MISSING_HISTORY (or an equally explicit non-PASS state). A strict
history/release gate fails or blocks; it must not silently skip and pass. Document
an explicit fetch/deepen or bundle-import remedy, but do not auto-fetch during
normal operation. Do not claim a source ZIP and a fully audited Git clone are the
same kind of evidence. Test command exit statuses as well as report text.

Disable Git replace-object behavior for exact-object audits and reject/explicitly
handle grafts and shallow/incomplete state. Test missing objects, moved tags,
wrong authority, missing artifacts, and tampered reconstruction/registry data.
Archive export must reject destination collisions and unsafe path traversal or
symlink escapes; do not write through untrusted archive paths.

### 6.4 Runtime evidence is retained, not blindly archived

Keep `models/` and current `variation/` data at their public paths. Initially retain
byte-exact source decisions required by a profile at their existing paths, even if
those paths contain historical names. A few justified runtime exceptions are better
than breaking profile hashes for cosmetic directory purity.

A current normative reference may be retained or moved with exact content and an
explicit locator mapping, provided no runtime/hash-bound path is broken and current
guides link correctly. Do not silently rewrite the scientific contract while
calling it a moved historical document.

## 7. Current architecture and compatibility boundary

Separate responsibilities rather than rewriting every module:

- Scientific runtime: catalog, model execution, extraction, comparison, noise,
  variation and replay. Avoid numerical edits and cosmetic broad reformatting.
- Current validation primitives: process/log handling, local input/provenance
  checks, report writing and current regression checks used by current workflows.
- Current release lifecycle: phase and candidate identity, required gates,
  clean-clone evidence, and the separate exact-tag gate.
- History operations: inspect/verify/export exact old releases; no import of their
  historical Python implementations into the live runtime.

Promote shared helpers out of old release modules into a small maintained module
where genuinely needed. Preserve helper behavior with tests and origin attribution.
Historical code remains exact in its authoritative tree; promoted current code is
not falsely labeled the original frozen validator. Do not replace one large
historical module with another large generic framework.

Project discovery must use current project identity/resources, not a release-era
file. Reuse `pyproject.toml` project identity and required current assets where
sufficient; do not add a second independent model catalog or dozens of markers.
Keep `APM_REPO_ROOT` and `APM_STATE_DIR` working with clear, tested precedence.
Reject an invalid explicit root rather than silently selecting another checkout.

Preserve documented scientific CLI operations, parameters, model include paths,
selectors, output field meanings and saved-realization semantics. Treat previously
undocumented Python imports as internal, but document any known integration impact.
Do not use a major version as permission to rename every working command.

Old historical release flags on current main must never run a current validator
and label its result a v3/v4/v5 qualification. Prefer an explicit nonzero migration
diagnostic giving the exact historical checkout/procedure. The original flags and
behavior remain available in their exact historical source. Any live dispatcher
must be an explicit, isolated operation with recorded source identity, not a hidden
fallback. Document this intentional maintainer workflow migration.

Saved realizations and run caches are different artifacts. Keep legacy realization
read/replay in its previously supported identical input/path context. Do not
promise arbitrary relocation. Preserve serialized draws/raw parameters and their
original evidence; do not rehash edited records to make them pass. New run/cache
identities caused by code/provenance changes are expected to be explicit and may
require fresh output, never acceptance of a stale cache.

## 8. Public documentation and maintainer guidance

All repository documents, prompts and reports are English.

Suggested short description:

> Open compact models and ngspice tools for analog device, noise, and mismatch studies.

Suggested introduction:

> Analog Process Models (APM) provides MOS compact models and ngspice-based tools
> for analog circuit research. Use the models in your own circuits, characterize
> devices, compare electrical families and technology classes, and study stationary
> noise and supported variation models.
>
> The collection combines redistributed open models with APM-authored generic
> models. It is a research toolkit, not a manufacturable PDK. Model provenance,
> supported ranges, and the limitations of each type of study are documented.

Refine against actual capabilities, not hypothetical future ones. Distinguish
upstream-derived and independently authored generic models in the small catalog.
Keep uncertainty and support caveats beside the relevant feature. Avoid repeating
all disclaimers or the release history in every page.

Required guide roles, reusing existing pages where possible:

- README: short introduction, model overview, useful tasks, start links, brief limits.
- docs/index: task navigation, current references, maintainer entry, history entry.
- getting started: prerequisites, cold setup, verified reuse, first useful result.
- using models: actual nominal model-in-circuit example, terminals/sizing/includes,
  native versus OSDI requirements; no release qualification needed for first use.
- characterization: commands, actual output files/units, interpretation/comparisons.
- noise: one useful device run, actual PSD fields/units, fits/unavailable states.
- variation overview: Benchmark vs Native vs Research and the corresponding guides.
- research local: sample once, run/replay, geometry/temperature limits, failure rules.
- models/sources/limits and Spectre status: current explanation plus exact references.
- maintainer entry: current validation, environment, phase/release and archive policy.
- migration/history: old-to-new locations/workflows and exact source/evidence links.

A simple Markdown navigation structure is enough. No website generator, hosted
site, translation system, logo, bilingual duplication or new platform support.
Target README about 600-900 English words excluding tables/commands, STATUS a short
snapshot, AGENTS a concise set of non-negotiable rules with task-specific links.
These are editorial goals, not arbitrary hard byte limits.

AGENTS may now be reorganized beyond the v5.1 narrow edit. Preserve its substantive
security, model/source, approval, Git and integrity rules. Relocate detailed release
identities to the verified history index and environment details to their current
guide, with clear mandatory routing. GOAL states this active mission; STATUS reports
what actually passed and what is currently blocked. Neither is a second release log.

Do not maintain strict tests for paragraphs of historical prose in README. Test
factual tables, links/anchors, designated critical boundaries and current lifecycle.
Keep a human-readable source-linked editorial review; keyword checks cannot prove
arbitrary prose true. Do not scan all historical text to satisfy a missing current
explanation. Preserve file-level licenses, notices and adaptation credits.

Prepare a consistent package/About description. Change GitHub About only when that
specific external write is authorized and available; an unapplied proposed description
is a separate report item, not a reason to alter unrelated repository settings.

## 9. User-journey acceptance

Every tutorial states working directory, prerequisites, actual commands, output
locations, what to inspect, and what the result does not establish. Execute the
same reviewed blocks that are published, not a different private command script.
Do not automatically execute arbitrary Markdown fences or historical release commands.

Required journeys:

J1. First-time visitor identifies available models, their origin, real backend,
    intended use and non-PDK boundary without understanding release gate terminology.
J2. Cold setup in an empty project-local prefix produces a real bounded result.
    Record required external dependencies. Hash-verified download caches are allowed;
    copied installed compilers/environments are not a cold bootstrap.
J3. Returning user safely reuses a verified toolchain, reconciles editable Python
    identity and runs current checks without destroying an existing prefix.
J4. A minimal APM045 native nominal circuit uses the actual public wrapper and
    include closure. An OSDI-backed example demonstrates its additional real needs.
J5. Characterization/comparison and device noise produce documented fields/artifacts,
    with a small interpretation drawn from actual output, not invented numbers.
J6. Benchmark, Native and Research choices are distinct; execute one appropriate
    supported example of each, without promising all-family measured MC.
J7. Save one Research realization and replay at another temperature/analysis without
    changing draws/raw values. Also test baseline-to-v6 replay under the existing
    path/input constraints. Fresh output does not mean a fresh device.
J8. Unsupported family, corrupt realization, stale cache, wrong root, occupied
    output and missing history give accurate diagnostics and safe recovery.
J9. A maintainer verifies and exports a historical release plus its evidence authority
    while working on v6, without modifying the checkout or executing old code by accident.
J10. A configured source snapshot with no `.git` can perform ordinary supported use,
     while strict history verification honestly remains unavailable.

At least a useful destination for each primary user task should be within two links
from README. Do not build chains of index pages. Preserve links to current applicable
contracts; do not bury everything frozen under an 'obsolete' heading.

## 10. Validation design

Separate normal current checks, selected real-tool regressions, historical integrity,
and release qualification. Keep unflagged `apm validate` as a clear current-maintainer
entry. Its report must identify its requested scope and any unavailable history or
tool check. Missing a required check cannot produce an overall success.

A smaller explicitly scoped product check may succeed without Git history, but its
report must not imply archive or release qualification. Implement the smallest
useful command/options; avoid inventing a generic validation DSL or plugin registry.

Prefer one phase-aware release coordinator with data for the current release over
new v3/v4/v5/v6 implementations importing each other. A gate should be a concrete
check, not an identifier plus an unverified supplied PASS string. Candidate and
exact-tag paths must be implemented and tested before candidate freeze.

Avoid recursive orchestration: pytest must not call the full release validator,
which calls current validation, which calls pytest. Unit-test coordinators using
fixtures; run the real-tool and archive journeys at an outer layer.

Map old checks into one of: preserved current check, equivalent current replacement,
or retained historical check run against its original source. No required scientific,
licensing or corruption test disappears without a visible, justified disposition.

## 11. Scientific compatibility and confirmation

This architectural release changes enough routing/validation code to require more
than a documentation smoke run. Freeze a machine-readable plan and tolerances before
confirmation, with exact baseline inputs and a reviewed allowed-change inventory.

Required compatibility work:

- All scientific model/profile/source assets retained in current use are byte-exact
  at stable public paths. Report any permitted non-scientific metadata delta separately.
- Trace all changed production modules and their transitive scientific dependencies.
  Keep numerical algorithms unchanged wherever possible. Routing/helper relocation
  must be tested, not assumed harmless because a function body looks similar.
- Run same-input baseline/v6 comparisons in isolated environments on the same
  observed tools. Compare physical outputs, failure classifications and required
  provenance, not only exit code or equal-looking table summaries.
- Compare exact arrays where deterministic and appropriate. Predeclare tolerances
  otherwise. Restrict exclusions to identified non-scientific identity/path/timestamp
  fields; never strip model/method/seed/tool integrity fields to get equality.
- Check deterministic latent draws, targets/raw realization values, Benchmark/native
  semantics, saved-realization replay, and stale/corrupt cache rejection.
- Run all-family electrical characterization through current code, the actual
  Benchmark/native checks, and the stationary-noise method/catalog coverage used by
  the supported current flows. Keep missing/unreachable states honest.
- Re-execute the v5 numerical Research confirmation matrix against the v6 runtime:
  65,536 artificial sampler pairs; N/P 11 geometries and 572 total mapping targets;
  4,096 SPICE pairs per geometry/polarity (90,112 total); 12 circuit families times
  1,024 realizations; same-realization replay and charge checks; IO assessments.
  Verify these counts against the original committed plan before using them.

The last item is a *v6 execution of the preserved numerical methodology*, not a
reinterpretation or edit of the historical v5 release validator. Promote the needed
current qualification helpers/plan access with clear provenance. Do not patch the
old version check to run historical code as if it were a v6 validator.

The independent Hart source decision and coefficients are not reopened or retuned.
Existing source evidence remains historical evidence; current numerical recovery
is software/transfer-model confirmation, not new silicon validation. Retain old
failed runs and current failures. No lucky seed search, clipping, redraw, discarded
samples or post-hoc tolerance relaxation.

For historical reconstruction, test exact source/evidence export, original package
identity and isolated representative execution. Do not claim a full old 16/17-gate
requalification unless actually executed. Local Git worktrees are useful development
isolates but share a repository; they do not establish the independently fresh
GitHub-clone condition of a release gate.

If an actual scientific defect is found, preserve a minimal reproducer and its
impact. Do not turn this task into a silent physics fix. Finish independent migration
and documentation work, and report a candidate blocker when the invariant cannot
be met. Infrastructure-only repairs within the declared boundary are allowed with
new evidence; unknown provenance is never a passing substitute.

## 12. Release gates and lifecycle

Use one v6 acceptance manifest. Required candidate gate groups:

| ID | Required evidence |
| --- | --- |
| identity.lifecycle | Coherent source/runtime/installed/CLI version and exact phase/commit/tree. |
| preservation.history | Full old identity/inventory coverage, no changed tag/release, authority reconstruction. |
| preservation.current_assets | Runtime model/profile/source/notice closure preserved and locally available. |
| architecture.dependencies | No live dependency on historical release implementations or markers; mapped helper/test migration. |
| docs.usability | Executed journeys, accurate output interpretation, links/anchors/claims/license review. |
| compatibility.science | Same-input comparisons, current electrical/noise/variation coverage and full declared Research matrix. |
| validation.fail_closed | Corruption, missing evidence, wrong phase/version/tag, scope and partial-run negative controls. |
| environment.reproducibility | Cold setup and safe warm reuse distinguished; observed tool/source receipts and fresh outputs. |
| quality.current | Required current tests, lint, REUSE, provenance/public hygiene and package/install checks. |
| release.clean_candidate | Exact clean candidate independently reproduced from authoritative fresh clone; all linked evidence validated. |

All ten groups must pass; subordinate required checks may not be collapsed away.
Freeze exact required check IDs/coverage before confirmation, not only these labels.
Add separate post-tag `release.exact_tag_requalification` from the outset. Unknown,
missing, skipped, stale, duplicate or empty required results fail closed. An expected
negative control passes only when its particular failure mechanism is demonstrated.

Implementation identity: `6.0.0.dev0`.
Frozen candidate identity: `6.0.0`.
Autonomous stop: `V6_RELEASE_READY` with exact commit/tree and evidence.
No tag or release publication is authorized by this handoff.

Before candidate freeze, unit/integration-test exact-tag orchestration with temporary
repositories and synthetic tags there, not a real `v6.0.0` tag in the project/remote.
After separate real approval, the intended flow is one immutable annotated `v6.0.0`
at the approved candidate, fresh exact-tag execution, then publication only on success.
Do not move/delete/recreate a failing tag. Post-tag is not a candidate prerequisite.
`6.0.0+main` is reserved for maintenance after actual publication.

The new release source will contain its coordinator and plans. Evidence emitted after
qualification names its subject candidate; committing the summary later does not
qualify that evidence commit. Exact Git tree identity is required even when Python
version strings match. Use a reviewed dependency set and observed compiler identity.

Do not freeze live README/user guides permanently on main again. Future historical
identity belongs to exact source/evidence records; current normative data still has
its own scientific integrity constraints. Test next-release extensibility using
synthetic fixtures, without creating a real v7 plan/release or building an abstract
framework for hypothetical versions.

## 13. Execution sequence

A. Inspect current state, run feasible baseline checks, capture old protected and
   scientific inventories and dependency maps. Record existing unrelated failures.
B. Commit coherent v6 mission/lifecycle/migration policy and predeclared acceptance
   plan. Preserve a usable path through the transition; do not leave main with
   knowingly contradictory mission/version checks.
C. Implement and test history identity/reconstruction in parallel with retained
   live-copy checks. Verify bundle restoration and runtime asset classification.
D. Decouple current project discovery, shared validation helpers and CLI routing.
   Promote current tests/qualification helpers with origin and equivalence evidence.
E. Remove/relocate only classified historical live copies whose preservation and
   dependency conditions now pass. Update current references; no broad tree deletion.
F. Complete current docs/AGENTS/GOAL/STATUS and executable user journeys, including
   archive/no-Git/returning-user and failure paths. Keep changes behavior-focused.
G. Run the full new confirmation, old/new compatibility and fault-injection plan.
   Fix in-scope implementation defects with retained failed evidence and reviewed
   changes; do not weaken science or archive gates to finish.
H. Commit/push coherent progress with normal fast-forward history. Freeze the clean
   6.0.0 candidate and execute all required v6 gates in a fresh authoritative clone.
I. Commit compact result references separately when appropriate. Stop only at
   V6_RELEASE_READY or a precise evidenced blocker after independent work completes.

Development subagents may own disjoint documentation, archive tests and dependency
analysis. One integrator owns the mutable instruction/version/gate/index files and
candidate freeze. Do not let parallel workers race on main or share writable output
folders. Use explicit simulator thread count and bounded worker parallelism, not
nested oversubscription. The user being offline is not permission to change scientific
scope, hide a failure, publish, or substitute an arbitrary source.

## 14. Stop conditions and report

Material blockers include unresolved history identity, lost artifact/notice closure,
unsafe migration of a runtime dependency, scientific drift, incompatible saved
realization behavior, unavailable reference tool provenance, failure of required
confirmation, or inability to reproduce the exact clean candidate.

Continue independent tasks where useful, without claiming release readiness. Keep
stable commits and exact blocker evidence. Do not repeatedly perform preflight
instead of implementation; do not request repeated approval for the authorized
in-scope operations. A later tag/publication is deliberately separate.

Final report must state:

- actual starting main and exact tested candidate/tree;
- later evidence commit and normal history relation;
- current documentation and maintainer-workflow changes;
- migrated artifact counts and exact inventory/reconstruction evidence;
- retained runtime/evidence exceptions and why they remain;
- changed production/helper modules and old-to-new test/check mapping;
- unchanged scientific assets, baseline/v6 comparisons, executed denominators,
  negative controls, failures and unavailable checks;
- cold versus warm environment evidence and observed pinned tool identities;
- all required gate results and reconstruction/bundle verification references;
- unapplied external metadata proposal and remaining limitations;
- explicit confirmation that no v6.0.0 tag or GitHub Release was created.

Keep the implementation small enough to understand. The deliverable is less coupling
and clearer use, not a larger collection of mutually dependent policy documents.

## Planning evidence and external technical references

This plan is grounded in GitHub connector reads at the reviewed commit, including
`src/apm/paths.py`, `src/apm/cli.py`, `src/apm/maintenance_validate.py`,
`src/apm/research.py`, AGENTS/GOAL and the current documentation/test/packaging
records discussed in the preceding review. The earlier v5.1 handoff was read fully
and its user-journey work is retained; its prohibition on an archive/dependency
migration is specifically superseded by this v6 plan.

Primary references for the proposed tooling semantics:

- Git worktree: https://git-scm.com/docs/git-worktree
- Git bundle: https://git-scm.com/docs/git-bundle
- Git clone: https://git-scm.com/docs/git-clone
- Semantic versioning: https://semver.org/

Git-object hashes and a successful reconstruction do not prove that old simulation
results were correct or that external dependencies will be available indefinitely.
Likewise, internal refactoring alone does not require a SemVer major version. This
plan intentionally changes historical maintainer workflows and live artifact
locations while preserving scientific user semantics, and documents that boundary.

No repository edits, simulator executions, archive migration, candidate qualification,
tagging or release publication were performed while preparing this plan.
