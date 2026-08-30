# Third-party model policy and provenance

APM 2.0.0 is self-contained for transistor-model sources, but repository-level
licensing is never assumed to override a model file's own terms.

## Distribution rules

1. Every vendored third-party model file has an authoritative source, pinned
   revision, exact imported path, applicable license, retained notice, and
   SHA-256 declaration in the owning technology's `provenance.toml`.
2. Third-party files retain their upstream licenses. They are not relicensed
   under APM's Apache-2.0 project license.
3. Ambiguous files are excluded even if the surrounding repository appears
   permissively licensed.
4. Generated derivatives record source and output hashes and must be
   reproducible from committed generators.
5. Generated OSDI binaries and large simulator results are not distributed.
6. Official PTM/PTM-MG model cards are neither shipped nor valid numeric source
   material for the independently authored APM022 and APM016F parameters. They
   may be used only as local, non-redistributed comparison oracles.

## APM350

APM350 is an independently authored Apache-2.0 generic BSIM3 deck. No
third-party model card is shipped.

The `silicon-vlsi-org/eda-technology` SCN4M_SUBM candidate was audited at
commit `70c89ecac61bf3409322355463650775f5b29f5e`. Although the repository root
is MIT-licensed, the exact parameter file lacks file-level author, original
source, and permission evidence. APM therefore neither redistributes it nor
uses its numeric parameters. Only clearly licensed class-level Lmin, Wmin, and
VDD statements from the candidate repository README informed the documented
technology class. The rejection record and hashes are in
`models/apm350/provenance.toml` and `parameter_generation.md`.

## APM130

APM130 vendors an exact subset of IHP Open PDK SG13G2 commit
`331c00484213b13414777eec1336ef5c29b969bd`:

- LV and HV PSP103 MOS model, corner, statistical, and mismatch libraries under
  Apache-2.0; and
- PSP 103.8.2/JUNCAP 200.6.2 Verilog-A sources under
  `LicenseRef-Si2-PSP-103.8.2`.

The cards identify PSP 103.6 and are executed with the pinned backward-compatible
103.8.2 engine. All imported upstream files remain byte-identical. Upstream Si2
terms, developer acknowledgements, notices, changelog, README, and release
notes are preserved, with the applicable terms reproduced under `LICENSES/`.

Generated LV and HV Spectre TT cards select the pinned QS model blocks, preserve
all selected parameter values and notices, rename only the OpenVAF module type
to Spectre's native PSP type, and fix wrapper-only inputs. Source/output hashes
and the deterministic generator are recorded in
`models/apm130/provenance.toml`. This transformation does not constitute real
Spectre validation.

## APM045

APM045 vendors the required nominal N/P VTL, VTG, VTH, and THKOX BSIM4 cards
from FreePDK45 1.4, Subversion revision 173, using the open-source-clean
`Chips4Makers/freepdk45` mirror commit
`688ee68ec5301e5fe11ebee5e53c1109d3cfd51d`.

The exact upstream README declares the files Apache-2.0 and states that
SVRF-EULA files were removed. APM preserves that README, the Apache-2.0 license,
and the model-basis manual. The shipped cards are byte-identical and every hash
is declared in `models/apm045/provenance.toml`.

The cards disclose customized PTM ancestry for this intentionally
upstream-derived predictive model set. That ancestry is not a license or
technical basis for APM022, whose values were independently authored.

## APM022

APM022's SVT deck, VTH0-isolated LVT/HVT variants, manifests, wrappers, and
variant-generation records are APM-authored Apache-2.0 assets. Public
literature and BSIM4 specifications establish dimensional context, parameter
semantics, and observable behavior targets. Official PTM22 card values were not
copied, transcribed, interpolated, fitted, optimized against, or otherwise used
as a numeric source.

The declared source inventory and independent-variant constraints are in
`models/apm022/provenance.toml` and `parameter_generation.md`.

## APM016F

APM016F's SVT parameter deck, PHIG-only LVT/HVT variants, manifests, wrappers,
and generation records are independently authored Apache-2.0 assets. They use
the UC Berkeley BSIM-CMG 112.1.0 engine released 2026-04-28 under ECL-2.0. The
engine's exact `LICENSE.txt`, `NOTICE.txt`, archive hash, and unmodified
Verilog-A sources are preserved and declared in
`models/apm016f/provenance.toml`.

Official PTM-MG16 card values were not copied, transcribed, interpolated,
fitted, optimized against, or otherwise used as a numeric source.

## Automated release audit

`apm provenance-check` verifies the complete shipped model inventory and
hashes, retained upstream license/notice boundaries, APM022/APM016F independent
authorship records, family binding closure, generated-output declarations,
Spectre claim boundaries, and repository-wide REUSE/SPDX compliance.

The release validator also rejects missing local includes, remote model
dependencies, generated binaries or raw results in Git, undeclared shipped
model files, oversized artifacts, credential signatures, or a provenance
manifest whose filesystem inventory differs from its declarations.
