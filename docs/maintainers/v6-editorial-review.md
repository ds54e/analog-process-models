# Current-guide editorial review for v6

This is a source-linked review of current guidance. The qualification report adds
observations from executing the named blocks at its exact candidate commit. It
does not treat a keyword scan as proof of arbitrary prose.

| Claim or task | Authority and review |
| --- | --- |
| Five technologies, fifteen families, thirty public devices | [Catalog loader](../../src/apm/catalog.py) and local `models/*/technology.toml` / family manifests; the README table uses native planar W/L or FinFET L/NFIN and identifies native BSIM4 versus OSDI PSP103/BSIM-CMG. |
| Model origin and use limits | [Provenance and license account](../../THIRD_PARTY.md), [APM045 positioning](../../APM045_POSITIONING.md), and each local provenance manifest; redistributed APM130 and FreePDK45 APM045 cards are distinguished from APM-authored generic APM350/APM022/APM016F and APM045 IO18/IO25 parameters. No manufacturable-PDK, silicon calibration or foundry/yield claim is made. |
| Cold setup and returning user | [Bootstrap](../../tools/bootstrap-el9.sh), [Python setup](../../tools/setup-python.sh), [observed compiler receipts](../../src/apm/compiler_provenance.py); external host prerequisites are stated, cold prefixes start absent, and warm setup preserves the existing compiler. The reference platform remains EL9 x86_64 WSL2. |
| Nominal public model use | [APM045 circuit](../../examples/nominal/apm045.cir) and [APM130 circuit](../../examples/nominal/apm130.cir) use actual public wrappers and model includes. The PSP example explicitly loads its two required OSDI modules. Paths are relative to the documented working directory. |
| Characterization and comparison | [Result contract](../../RESULT_CONTRACT.md) and [implementation](../../src/apm/characterize.py); guides identify raw signed terminal data, finite-difference gm/gds, native sizing and capacitance from complex terminal Y. Actual result fields and numeric interpretations are inspected by [the journey evaluator](../../src/apm/journeys.py). |
| Stationary noise | [Noise contract](../../NOISE_CHARACTERIZATION.md), [fit/acquisition contract](../../NOISE_N1.md), [catalog methodology](../../NOISE_N2.md); `noise_model_snapshot.json` is the actual effective-parameter artifact. PSD units and complex transfer agree with the generated schema. Unavailable fit regions and unreachable requests remain explicit. |
| Benchmark / Native / Research | [Benchmark contract](../../variation/benchmark_v2.toml), [native contract](../../models/apm130/families/lv/family.toml), [Research contract](../../V5_RESEARCH_VARIATION.md); guides distinguish synthetic intent sampling, upstream native process/mismatch semantics and optional VTG local transfer-hypothesis parameters. No measured all-family MC is promised. |
| Source and mismatch limits | [Retained source decision](../../validation/evidence/v5_source_decision.md) and [registry](../../variation/research/apm045/sources.toml); original beta blockage, transferred-coefficient uncertainty, unsupported IO/default profile and off-reference-temperature limits remain explicit. |
| Save and replay | [Research runtime](../../src/apm/research.py) and [SPICE runner](../../src/apm/research_spice.py); temperature and recipe changes preserve raw devices. Identical path/input legacy replay is tested separately; relocation is not promised. Corrupt physical records are never rehashed as a migration. |
| History and no-Git source use | [Exact index](../../releases/index.toml), [inventory](../../releases/migration-v6.json), [current root discovery](../../src/apm/paths.py), [history implementation](../../src/apm/history.py); old release workflows move to their exact source and evidence authorities. Product-only scope does not claim missing archive verification. |
| Spectre | [Structural checker](../../src/apm/spectre_validate.py) and local backend manifests; model-only experimental/unverified, with no real execution or numerical equivalence claimed. |
| Lifecycle and external metadata | [Acceptance manifest](../../validation/acceptance.toml) and [maintainer entry](index.md); exact candidate and later evidence commits are distinct. No real tag/release is authorized. The package description is applied locally; the same GitHub About proposal remains unapplied. |

All primary task guides are reachable within two links from README. Current links
and heading anchors are checked separately. Frozen normative scientific documents
remain available beside current tutorials. Historical prose is assessed in its
original source context and is not rewritten to pretend it describes v6.
