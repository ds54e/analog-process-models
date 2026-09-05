<!-- SPDX-FileCopyrightText: 2026 APM contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Research local variation (v5 development)

This optional flow applies individual VTG N/P threshold/current-factor changes.
The Hart/TSMC40 companion adaptation is a quantitative **transfer hypothesis**;
it is not foundry correlation, silicon calibration or yield prediction. The
original Hart/ST40 beta remains blocked. See the [source decision](../validation/evidence/v5_source_decision.md)
for the geometry inference, units, extraction convention and uncertainty limits.
The implementation is undergoing candidate qualification; v5 is not released.

From a configured repository checkout:

```sh
apm research describe
apm research sample --profile variation/research/apm045/derived/hart_tsmc40_profile.json \
  --request examples/research/request.json --seed 1001 --index 0 \
  --state .apm/v5/example/maps --output .apm/v5/example/realization.json
apm research run --request examples/research/request.json \
  --realization .apm/v5/example/realization.json --output .apm/v5/example/runs
apm research run --request examples/research/request.json \
  --realization .apm/v5/example/realization.json --temperature-c 85 \
  --output .apm/v5/example/runs
apm research check --suite all --output .apm/v5/confirmation
```

The example is a hierarchical 1:1 mirror with explicitly ideal reference, supply
and output clamp. Copy its request and circuit to author another circuit.
A circuit file contains the body and subcircuits; the runner supplies the control
block, model includes and final `.end`. Local includes are recursively resolved
and hashed. Known nominal VTG model redefinition is rejected. Analysis recipes
contain typed DC, AC, transient or operating-point settings and terminal vectors;
`set_sources` declares finite voltage/current source settings before an analysis.
A source setting does not change a saved MOS realization. The user remains
responsible for the operating domain of an authored circuit.

Every physical MOS gets a unique `uid`, wrapper hierarchy `path`, family,
polarity and exact `w_m`/`l_m`. Paths are hierarchy segments, not SPICE commands.
`other_variation_leaves` declares existing Benchmark/native assignments;
overlap is rejected. Unit banks need one UID and wrapper per physical unit.
`m=N`, width multiplication and repeated identical draws are not independent units.

New schemas use `apm.research-{request,profile,realization,map,run,report}.v1`.
Saved records contain their hash, the actual standard-normal draws, requested
observable changes, resolved raw DELVTO/ln(MULU0), mapping/profile identity,
physical-device identity and bound circuit/includes. Sampling keys contain root
seed, sample index, UID and channel. Adding/reordering devices or workers cannot
change an existing draw. Changing geometry with the same UID shares random
numbers but creates a different physical realization. The serialized draws and
raw values are the replay authority; RNG cross-version identity is not promised.

Mapping uses a full N/P reference Jacobian and a bounded polynomial inverse at
300 K, |VDS|=50 mV, VBS=0, plus actual fine-grid verification during public sampling.
The reference MG coordinate uses a cubic-spline maximum-gm tangent and D/2
subtraction. It does not replace canonical finite-difference gm/gds or VTH_CC.
After sampling, bias, temperature and analysis changes do not refit raw parameters.
Outside the supported W=1–4 um, L=.12–.40 um rectangle or joint +/-6-sigma domain,
nonpositive beta, missing peaks and failed inversions are explicit failures.
They are never clipped, redrawn or removed from a campaign denominator.

Each uncached run is a fresh ngspice 47 process with one thread, normal Sparse,
model/geometry/raw readback and a separate output directory. Readback is repeated
around every analysis. A zero exit code is insufficient. Caches require bound
input and output hashes; changed or incomplete data fail. To retry a failed
sample, retain it and select another output directory with the **same** saved
realization. A new seed is another physical draw, not a retry.

Source intervals, PDF-digitization bounds and unquantified process/interpolation
transfer uncertainty remain separate from the within-device random model. The
independent-Croon rho=0 approximation is named explicitly. The population-beta
pair statistic and actual pair-average ratio are reported separately.
Temperatures away from 300 K are uncalibrated predictions. Global/spatial effects,
SS/weak-inversion calibration, passives, noise MC, foundry/yield claims and all
other families are unsupported. IO18/25 have an assessment only; unknown beta is
not zero. No default IO mismatch profile is supplied.

Artificial fixtures require `--allow-artificial` and retain that tier in every
realization. They cannot satisfy the quantitative-source release gate.
The committed confirmation plan separates small development cohorts from the
full cohorts beginning at sample index 1000000, and declares confidence,
equivalence and failure policies before execution. Source reanalysis additionally
needs the optional `research-audit` dependencies and the explicitly provided,
hash-matching PDF; runtime sampling performs no web access.
