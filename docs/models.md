# Models, sources and limits

The [README catalog](../README.md#model-overview) summarizes all five technologies
and fifteen families. Each technology's `technology.toml` and family manifests are
the discovery authority; `provenance.toml` inventories every shipped model input.
Use `apm describe technology/family/device` for public names, backend bindings,
geometry and Operating Profiles.

APM130 redistributes the pinned IHP SG13G2 MOS subset and PSP103 engine with their
own licenses. APM045 VTL/VTG/VTH/THKOX preserve the audited FreePDK45 nominal cards.
APM350, APM022, APM016F parameter decks and APM045 IO18/IO25 are independently
APM-authored generic models. APM016F uses the separately licensed BSIM-CMG engine.
Official PTM/PTM-MG cards are not numeric source material for APM022/APM016F.
Exact revisions, file-level terms, notices and PSP acknowledgements are in
[THIRD_PARTY.md](../THIRD_PARTY.md) and the technology provenance manifests.

APM045 means a generic 40/45 nm-class research environment, with the technical
45 nm FreePDK45-based namespace preserved. Public TSMC process descriptions were
post-release taxonomy context only, not numeric input or fitting targets for the
released IO model-generation flow. Read [APM045 positioning](../APM045_POSITIONING.md).
The retained IO model-construction ensemble describes uncertainty in construction;
it is not a device/process population. Its reproducible generator, normative
contracts and evidence closure stay available locally.

An Operating Profile is a study choice, not a fabrication or reliability rating.
Model-supported geometry and the characterized envelope are distinct from foundry
design rules. Missing validity information remains unknown. Native planar W/L and
FinFET L/integer-NFIN are separate bases; per-width and per-fin quantities are not
silently equated.

The Research companion-source adaptation is licensed and credited separately from
APM code. Its [hashed decision](../validation/evidence/v5_source_decision.md),
[registry](../variation/research/apm045/sources.toml) and derived profile remain local,
including in source snapshots without Git. Source/digitization uncertainty is not
extra within-device randomness; transfer and interpolation uncertainty remain
unquantified. Original Hart/ST40 beta remains blocked, and IO statistical transfer
remains unresolved. See [variation choices](variation.md).

APM is not a manufacturable PDK. It provides no layout, PCells, DRC/LVS/PEX,
standard cells, signoff, yield or reliability qualification. Model execution does
not establish silicon calibration. [Spectre](spectre.md) is model-only,
experimental/unverified; there is no real Spectre or Virtuoso integration claim.
