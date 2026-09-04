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
  --config tools/modelgen/apm045_mixed_voltage/generation_epoch_2.toml \
  --output .apm/results/v4-generation-epoch2-calibration \
  --calibration-only
```

Then run the repeatable, non-holdout seal audit:

```bash
.venv/bin/python -m tools.modelgen.apm045_mixed_voltage.qualify_families \
  --config tools/modelgen/apm045_mixed_voltage/qualification_epoch_2.toml \
  --calibration-report .apm/results/v4-generation-epoch2-calibration/report.json \
  --output .apm/results/v4-qualification-epoch2-preflight \
  --preflight
```

`--unseal` is accepted only from a clean committed tree and an empty output
directory. It writes the unseal receipt before the first holdout job and does
not accept `--replace-output`. Candidate parameters are immutable throughout
qualification, and medoid selection occurs only after circuit results.

Epoch 1 is retained as failed-closed history. Its strict method rejected io25
when 17.5 1/V was explicitly not reachable in subsets of the high-temperature
qualified-current region. Epoch 2 uses disjoint seeds and new holdout
definitions; it implements the release contract's explicit
`target_not_reachable`/near-off states while still requiring two qualified
intermediate inversion targets on every curve. Neither old coordinates nor old
candidates are reused for repair.

## Claim boundary

Successful reconstruction establishes that the fitting machinery can recover
specified held-out terminal behavior from known models. It does not validate
a new family, recover a reference model's original parameters, provide foundry
or silicon correlation, or establish voltage reliability, geometry rules, or
manufacturability. New-family model generation and its sealed device and
circuit holdouts are separate v4 gates.
