# Third-Party Model Policy

APM v1.0 is intended to be self-contained, but it must not redistribute model assets without clear authority.

## Rules

1. Every vendored third-party model file must have an auditable upstream source, exact revision, and original license.
2. Third-party files are not relicensed under the APM root Apache-2.0 license.
3. Upstream copyright and license notices must be preserved.
4. If redistribution rights are ambiguous, the file must not be shipped.
5. Prefer a clearly redistributable alternative or an independently authored APM model over ambiguous material.
6. Official PTM/PTM-MG model cards are not to be redistributed in v1.0 unless a future authoritative redistribution review explicitly changes that packaging decision.
7. **Separately from licensing**, APM022 and the APM016F parameter deck must remain independently authored as required by `GOAL.md` and `AGENTS.md`. Even if PTM/PTM-MG redistribution rights were later clarified, their numeric model-card parameters are not valid source material for those APM-authored v1.0 decks. PTM/PTM-MG may be used only as local, non-redistributed sanity/comparison oracles.

## Planned provenance

### APM350

Candidate: open generic SCN4M_SUBM-class model. Exact source files and license must be verified before vendoring.

### APM130

Source: IHP SG13G2 Open PDK simulation subset. Preserve Apache-2.0 and any model-specific upstream terms exactly.

### APM045

Source: open-source-clean FreePDK45 simulation subset. Verify exact imported files and headers before release.

### APM022

APM-authored BSIM4 parameter deck. Public literature and compact-model specifications may inform behavior targets. Official PTM22 may be used only as a local non-redistributed sanity/comparison oracle and is not numeric source material for the deck.

### APM016F

APM-authored parameter deck using a pinned redistributable BSIM-CMG implementation. Preserve the exact Berkeley/upstream license text of the chosen source revision. Official PTM-MG16 may be used only as a local non-redistributed sanity/comparison oracle and is not numeric source material for the deck.

## Release requirement

`provenance.toml` for every kit must be complete before v1.0.0. Every vendored third-party asset must be covered by exact provenance and applicable license/notice handling; repository-level license assumptions are insufficient.
