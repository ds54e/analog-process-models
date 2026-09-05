# Choose a variation flow

These flows answer different questions. Select one before sampling; do not combine
their perturbations on the same physical transistor.

| Flow | Supported scope | Meaning and guide |
| --- | --- | --- |
| Benchmark Global / Local / All | All 15 families; synthetic R/C | Deterministic comparison stresses and size law; [Benchmark](benchmark-variation.md) |
| Native | APM130 LV/HV MOS subset | Preserved IHP corner/process/mismatch library behavior; [Native](native-variation.md) |
| Research Local | APM045 VTG N/P, W=1–4 um, L=0.12–0.40 um | Source-derived VTH_MG/beta_MG transfer hypothesis with persistent physical realizations; [Research](research-local.md) |

Benchmark correlation is a comparison design, not physical foundry correlation.
Native LV/HV cross-family correlation is unspecified, and no native All mode is
invented. Research Global/All and statistical IO18/IO25 profiles are unavailable.
Unknown beta does not mean zero. No flow supplies all-family measured Monte Carlo,
yield prediction, calibrated temperature statistics or noise Monte Carlo.

The linked guides state working directory, prerequisites, exact commands, output
files and limitations. Save resolved Benchmark samples or Research realizations;
reusing the same seed alone is not a promise of replay across future RNG versions.
