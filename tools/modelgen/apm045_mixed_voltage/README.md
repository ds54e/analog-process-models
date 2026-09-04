# APM045 mixed-voltage model generation

This directory contains the deterministic, offline-only BSIM4 generation
kernel used for the APM v4 mixed-voltage work. It is development tooling, not
an import-time or run-time dependency of the installed `apm` package.

## Reconstruction prerequisite

Before generating a new device family, the kernel must reconstruct held-out
terminal behavior for both polarities of:

- `apm022/svt`, an APM-authored BSIM4 family; and
- `apm045/vtg`, the pinned open FreePDK45 thin-stack anchor.

The fitting objective receives simulator-produced terminal observations. It
does not parse or receive reference card parameters, and original parameter
recovery is not required. Drain current is measured at the external drain
source. gm and gds are finite differences of that terminal current. Cgg is
derived from terminal Ygg at 1 MHz using an independent 1 V small-signal gate
excitation; simulator-internal `@M[gm]`, `@M[gds]`, and `@M[cgg]` fields are not
fit inputs.

`reconstruction.toml` freezes the grids, unseen holdout coordinates,
acceptance criteria, parameter bounds, parameter-stage membership, and the
three deterministic seeds before execution. The five cumulative stages are
electrostatics, transport, output, charge, and temperature. Every simulator
failure, non-finite result, non-positive current or derivative, non-monotonic
curve, or non-positive terminal Cgg rejects the candidate rather than adding a
soft penalty.

## Execution

After `./tools/bootstrap-el9.sh` and `apm doctor` pass, run the complete
prerequisite from the repository root:

```bash
.venv/bin/python -m tools.modelgen.apm045_mixed_voltage.qualify_reconstruction \
  --output .apm/results/v4-modelgen-reconstruction
```

`--fixture` and `--polarity` are diagnostic filters. A filtered passing run is
labeled `MODELGEN_RECONSTRUCTION_SUBSET_PASS`; only an unfiltered report that
contains all four required records may emit `MODELGEN_KERNEL_QUALIFIED`.

Raw cards, terminal traces, netlists, logs, and the full report stay in the
ignored `.apm/` workspace. A release claim uses a compact committed evidence
summary bound to the generator, configuration, reference-model, tool, and
full-report hashes.

## New-family epochs

Calibration is separate from unsealing. Generate the current epoch's frozen
candidates without evaluating any holdout:

```bash
.venv/bin/python -m tools.modelgen.apm045_mixed_voltage.synthesize_families \
  --config tools/modelgen/apm045_mixed_voltage/generation_epoch_3.toml \
  --output .apm/results/v4-generation-epoch3-calibration \
  --calibration-only
```

Then run the repeatable, non-holdout seal audit:

```bash
.venv/bin/python -m tools.modelgen.apm045_mixed_voltage.qualify_families \
  --config tools/modelgen/apm045_mixed_voltage/qualification_epoch_3.toml \
  --calibration-report .apm/results/v4-generation-epoch3-calibration/report.json \
  --output .apm/results/v4-qualification-epoch3-preflight \
  --preflight
```

`--unseal` is accepted only from a clean committed tree and an empty output
directory. It writes the unseal receipt before the first holdout job and does
not accept `--replace-output`. Candidate parameters are immutable throughout
qualification, and medoid selection occurs only after circuit results.

Release requalification uses `--replay` with
`calibration_replay_v4.toml`. The first-unseal calibration hash remains
unchanged. The replay binding additionally fixes a portable science hash that
excludes only calibration time and the clone-local ngspice path, binary hash,
and build banner. A replay still requires those omitted tool fields to match
the fresh executable exactly, requires ngspice major 47, passes the unmodified
fresh report to the frozen qualifier, regenerates the same candidate cards
byte-for-byte, and reruns every device and circuit holdout. After verifying the
raw and portable identities, its narrow adapter changes only the frozen
qualifier's legacy canonical-hash callback to return the preserved first-unseal
hash. It changes no candidate parameter, holdout definition, electrical
criterion, electrical evaluation code, or first-unseal evidence.

Epoch 1 is retained as failed-closed history. Its strict method rejected io25
when 17.5 1/V was explicitly not reachable in subsets of the high-temperature
qualified-current region. Epoch 2 used disjoint seeds and new holdouts and
fixed that classification, but its extra all-candidate-pairs requirement then
rejected otherwise passing distinctness at 20 1/V. Epoch 3 again uses new seeds
and new holdout/structural/distinctness definitions. It requires two qualified
intermediate targets per device curve and at least half of candidate-pair
comparisons per distinctness view, polarity, and target, while persisting every
explicit `target_not_reachable` state. No failed holdout is used as a repair
target and no failed candidate is reused.

## Claim boundary

Successful reconstruction establishes that the fitting machinery can recover
specified held-out terminal behavior from known models. It does not validate
a new family, recover a reference model's original parameters, provide foundry
or silicon correlation, or establish voltage reliability, geometry rules, or
manufacturability. New-family model generation and its sealed device and
circuit holdouts are separate v4 gates.
