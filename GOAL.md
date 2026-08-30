# Post-v3.0.0 Public-Readiness and Maintenance

## Released state

APM v3.0.0 is already released and immutable.

- annotated tag: `v3.0.0`;
- tag object: `afecec29ea6ed0703ef441d4839fd40a238bef0b`;
- tagged commit: `995e0ce7cdd0c37ef9f3397008637f9d239c746e`;
- exact-tag post-release qualification: 18/18 PASS;
- GitHub Release: `Analog Process Models v3.0.0`;
- post-tag evidence:
  `validation/evidence/v3_post_release_requalification.json`.

No release artifact is being recreated under this goal. The released tags,
tagged commits, GitHub Release, model-card baseline, and hash-bound release
evidence remain unchanged.

## Goal

Prepare post-release `main` for a later, separately authorized transition from
private to public while keeping the repository private throughout this work.

This is documentation, public-hygiene, provenance, privacy, and maintenance
work. It does not authorize publicization, history rewriting, a package-version
change, a replacement tag, or a modified GitHub Release.

## Required outcome

1. Current policy, status, README, and validation documentation consistently
   describe v3.0.0 as released, tagged, exactly requalified, and published as a
   GitHub Release.
2. Candidate-era and milestone documents remain available as clearly labeled
   historical/frozen engineering records rather than active instructions.
3. The current tree and all reachable Git history receive explicit
   secret/privacy, generated-artifact, large-binary, and proprietary-model
   review.
4. PSP103/Si2, IHP, FreePDK45, and BSIM-CMG redistribution boundaries,
   acknowledgements, notices, exact source identities, and hashes are
   rechecked.
5. Public-facing `SECURITY.md` and `CONTRIBUTING.md` give practical reporting
   and contribution guidance without inventing private contact information.
6. Current claim-review hashes, normal validation, Pytest, Ruff, REUSE, and
   provenance validation pass after the cleanup.
7. Compact evidence is committed at
   `validation/evidence/public_readiness_v3.json` and `STATUS.md` records the
   evidence-based result.
8. Harmless repository description/topics may be improved while visibility
   remains private.

## Preserved technical and claim boundaries

Preserve the released v2/v3 architecture and schemas, including native planar
`w,l`, FinFET `l,nfin`, stationary external-terminal noise semantics, adaptive
bounded acquisition, fail-closed contiguous-region fitting, deterministic
catalog identity/resume behavior, and parameter-level model provenance.

APM remains not a manufacturable PDK. APM-authored model/noise predictions are
not silicon or foundry calibrated. No process-noise calibration, noise Monte
Carlo, transient noise, RTS/RTN, PSS/PNoise, oscillator phase noise, full
terminal noise-correlation matrix, reliability claim, universal
planar/FinFET-width conversion, or real Spectre validation is introduced.

## Stop conditions

Stop public-readiness completion rather than improvising if the audit finds an
actual credential, personal/private history artifact, proprietary model/PDK
asset, EULA-governed file, ambiguous redistribution right, or another issue
that would require history remediation. Do not rewrite history automatically.

## Completion state

Status: **COMPLETE**

The current-tree and whole-history audits passed, third-party redistribution
and acknowledgements were requalified, stale documents were classified,
SECURITY/CONTRIBUTING guidance was added, and the coherent cleanup commit passed
Pytest, Ruff, REUSE, provenance, public-hygiene, and normal repository
validation. Compact evidence was committed afterward. Released tags and the
GitHub Release remain unchanged, and repository visibility remains PRIVATE.

After completion, the only next action is human review and separate explicit
authorization to change repository visibility from private to public.
