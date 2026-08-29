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

The preferred `silicon-vlsi-org/eda-technology` SCN4M_SUBM parameter file was
audited at commit `70c89ecac61bf3409322355463650775f5b29f5e` and rejected. The
repository has an MIT root license, but the exact model card contains no
author, original-source, copyright, or file-level permission statement. It is
not vendored and none of its parameters was used.

APM350 instead ships an independently authored Apache-2.0 generic BSIM3 deck.
The pinned candidate repository README is used only for its MIT-licensed
class-level Lmin, Wmin, and VDD statements. The complete audit and exact
rejected-file hash are in `models/apm350/provenance.toml` and
`models/apm350/parameter_generation.md`; APM350 has no third-party files.

### APM130

Pinned source: IHP SG13G2 Open PDK commit
`331c00484213b13414777eec1336ef5c29b969bd`. The vendored subset contains only the
low-voltage MOS ngspice cards (Apache-2.0) and the PSP 103.8.2/JUNCAP 200.6.2
Verilog-A source package (`LicenseRef-Si2-PSP-103.8.2`). The model cards identify
PSP 103.6; they have been tested with the newer backward-compatible engine.
Vendored upstream files remain byte-identical. A generated Apache-2.0 Spectre
derivative selects the IHP TT N/P QS blocks, preserves all selected parameter
values and notices, changes only the OpenVAF model-type name `psp103va` to the
native Spectre name `psp103`, and fixes wrapper-only inputs. Its generator,
transformation record, source hashes, and output hash are in
`models/apm130/provenance.toml` and `docs/spectre.md`.

### APM045

Pinned source: FreePDK45 1.4 from the open-source-clean
`Chips4Makers/freepdk45` Git mirror, commit
`688ee68ec5301e5fe11ebee5e53c1109d3cfd51d`. The exact upstream root README
states that all files are Apache-2.0 and records that SVRF-licensed files were
removed. APM ships only the byte-identical nominal VTG NMOS/PMOS BSIM4 cards,
that README, the Apache-2.0 license, and the model-basis manual. Exact hashes
are in `models/apm045/provenance.toml`.

The model cards state that they are customized PTM-derived 45 nm cards. That
ancestry is disclosed for this deliberately upstream-derived predictive kit;
the values are not source material for the independently authored APM022 deck.

### APM022

APM-authored BSIM4 parameter deck. Public literature and compact-model specifications may inform behavior targets. Official PTM22 may be used only as a local non-redistributed sanity/comparison oracle and is not numeric source material for the deck.

### APM016F

APM-authored parameter deck using UC Berkeley BSIM-CMG 112.1.0, released
2026-04-28 and distributed under ECL-2.0. The exact upstream `LICENSE.txt`,
`NOTICE.txt`, and Verilog-A engine sources are preserved without modification;
the upstream archive SHA-256 is recorded in `models/apm016f/provenance.toml`.
Official PTM-MG16 may be used only as a local, non-redistributed sanity/comparison
oracle and is not numeric source material for the deck.

## Release requirement

`provenance.toml` for every kit must be complete before v1.0.0. Every vendored third-party asset must be covered by exact provenance and applicable license/notice handling; repository-level license assumptions are insufficient.
