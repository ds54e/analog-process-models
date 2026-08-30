# Post-v3.0.0 Public Maintenance

## Current state

APM v3.0.0 is released and immutable.

- annotated tag: `v3.0.0`;
- tag object: `afecec29ea6ed0703ef441d4839fd40a238bef0b`;
- tagged commit: `995e0ce7cdd0c37ef9f3397008637f9d239c746e`;
- exact-tag post-release qualification: 18/18 PASS;
- GitHub Release: `Analog Process Models v3.0.0`;
- repository visibility: PUBLIC.

The current tree passed a public-readiness audit before publication. That
historical pre-publication result remains at
`validation/evidence/public_readiness_v3.json`; the controlled visibility,
protection, and security transition is recorded separately at
`validation/evidence/publication_v3.json`.

## Goal

Maintain the public post-v3 repository without changing the meaning or
identity of the released v3.0.0 baseline. Future work occurs through normal
commits on `main` or reviewed contribution branches. Released tags, tagged
commits, the existing GitHub Release, model-card baseline, and hash-bound
release evidence remain immutable.

This stable maintenance goal does not create a v3.1, v4, calibration, or model
development milestone. A new technical or release goal requires a separate,
explicitly scoped task.

## Maintenance requirements

1. Keep the public README, policy, security guidance, status, provenance, and
   contribution documentation accurate.
2. Preserve active protection for `main`: branch deletion and non-fast-forward
   updates are blocked, while external contributions use pull requests and
   owner maintenance remains practical.
3. Preserve Private Vulnerability Reporting, secret scanning, and push
   protection unless a separately authorized security change is justified.
4. Keep normal current-tree validation, Pytest, Ruff, REUSE, provenance, and
   public-hygiene checks green for maintenance changes.
5. Record compact auditable evidence for material maintenance or security-state
   transitions without rewriting historical evidence.
6. Keep released tags and history immutable; use normal fast-forward pushes
   and never force-push.

## Preserved technical and claim boundaries

Preserve the released v2/v3 architecture and schemas, including native planar
`w,l`, FinFET `l,nfin`, stationary external-terminal noise semantics, adaptive
bounded acquisition, fail-closed contiguous-region fitting, deterministic
catalog identity/resume behavior, and parameter-level model provenance.

Public visibility does not change technical fidelity. APM remains not a
manufacturable PDK. APM-authored model/noise predictions are not silicon or
foundry calibrated. No process-noise calibration, noise Monte Carlo,
transient noise, RTS/RTN, PSS/PNoise, oscillator phase noise, full terminal
noise-correlation matrix, reliability claim, universal planar/FinFET-width
conversion, or real Spectre validation is implied by publication.

## Stop conditions

Stop rather than improvising if maintenance reveals an actual credential,
personal/private history artifact, proprietary model/PDK asset,
EULA-governed file, ambiguous redistribution right, released-tag discrepancy,
or another issue that would require history remediation. Do not rewrite
published history or alter a released artifact automatically.

## Completion state

Status: **ACTIVE MAINTENANCE**

The pre-publication audit and controlled publication are complete. Repository
visibility no longer awaits a decision. There is no active new-model,
calibration, package-version, or release objective.
