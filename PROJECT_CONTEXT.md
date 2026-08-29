# Project Context and Design Rationale — APM v2

This file records why the v2 contract looks the way it does. It is informative; `AGENTS.md`, `GOAL.md`, and `DEVICE_FAMILY_MODEL.md` are normative on conflict.

## 1. v1 outcome and why v2 exists

APM v1.0.0 successfully established five technology anchors and a reproducible terminal-level characterization/variation framework:

`0.35um-class planar -> 130nm planar -> 45nm planar -> 22nm-class planar -> 16nm-class FinFET`

v1 intentionally used one representative N/P family per technology. That was the right way to establish the simulator/toolchain/result methodology with limited scope.

The next technical limitation is now clear: real processes increasingly expose multiple nominal electrical device families within one technology, including low/high threshold options and thick-/thin-gate-stack options. Treating each technology as one VDD/Lmin/N/P pair is no longer an honest domain model.

v2 therefore changes the object of study from only **technology scaling** to both:

- cross-technology scaling; and
- within-technology electrical-family tradeoffs.

## 2. Why the redesign is breaking rather than compatibility-preserving

The repository has not been publicly adopted as a stable compatibility ecosystem. Preserving v1 aliases/schemas would make implementation more complex without real user benefit.

The v1 tag already preserves the complete validated historical release.

Therefore v2 is allowed to remove:

- one-family `kit.toml` SSOT;
- unqualified public wrappers;
- v1 result schemas;
- v1 benchmark adapter schema;
- technology-specific loaders superseded by the catalog.

The objective is the best long-term architecture rather than a migration layer.

## 3. Why Technology -> Electrical Family -> Device

Research across IHP SG13G2, FreePDK45, SKY130, GF180, and ASAP7 shows that several concepts often diverge:

- electrical model/parameterization identity;
- nominal/allowed operating voltage;
- threshold flavor;
- gate-stack class;
- N/P availability;
- DNWELL/isolation/layout option;
- RF/ESD/schematic view;
- usage such as core/IO/analog/standard-cell.

A single `device_type = core_lvt_io_thick...` taxonomy would eventually become contradictory.

The durable abstraction is:

- **Technology** — node/process namespace;
- **Electrical Family** — distinct nominal electrical parameterization;
- **Device** — simulated entity/polarity/geometry inside the family.

Operating Profile, Backend Binding, Variation, and Comparison Set are separate.

## 4. Why Family is electrical identity, not usage

IHP's thick-oxide 3.3 V MOS is useful for I/O but is also a high-voltage analog device. Calling the family `io` would encode one application as electrical truth.

GF180 shows 5 V and 6 V layout/device options mapping to the same electrical SPICE model, while DNWELL variants may also share a model.

IHP RF views can share base electrical models/modes rather than represent entirely new process families.

Therefore `core`, `io`, `rf`, etc. are descriptive use/view metadata when needed, not primary Family identity.

## 5. Why Operating Profile is separate from Family

A model family may support more than one useful operating profile, and a model-validity limit is not identical to a recommended/representative supply.

Three concepts are separated:

1. model validity evidence;
2. APM Operating Profile;
3. reliability/breakdown/lifetime rating.

APM v2 normally covers 1 and 2. It does not convert compact-model headers into reliability qualification.

This separation also prevents a future 5V/6V-style shared model from requiring duplicated electrical families just because two application profiles exist.

## 6. Why Devices need not be N/P symmetric

Open PDKs demonstrate sparse device sets: high-/native-threshold options can exist for only one polarity or have distinct geometry/validity ranges.

IHP HV already gives a practical v2 stress case because NMOS and PMOS have different minimum lengths.

Therefore family manifests list Devices explicitly; no schema rule requires one N and one P device.

## 7. Why APM130 comes first

APM130 is the strongest real/open anchor and its existing pinned IHP snapshot already contains both LV and HV model structures.

It tests several domain requirements at once:

- different gate stacks/operating profiles;
- different N/P Lmin values;
- real PSP/OSDI execution;
- native corners/statistical/mismatch;
- same upstream lineage without unnecessary source-revision churn.

If the family architecture works for APM130 LV/HV, it is less likely to have hidden one-family assumptions.

## 8. Why APM045 comes before generic multi-Vt

FreePDK45 supplies VTL/VTG/VTH/THKOX flavors. This provides a native/open dataset for:

- threshold-family Ion/Ioff tradeoffs;
- SS extraction-method testing;
- equal-bias/equal-inversion comparison design;
- gate-stack comparison design;
- realistic magnitude/trend context for generic APM022/APM016F multi-Vt variants.

Generic family targets should be chosen after observing native/open families, not before.

## 9. Why APM022 multi-Vt is threshold-isolated

APM022 is a generic educational/comparison model, not a foundry process recreation.

The most honest new capability is a controlled experiment where geometry/gate stack/basic physical basis stays common while nominal threshold class changes enough to produce the expected Vth/Ion/Ioff ordering.

This intentionally isolates a major multi-Vt design tradeoff rather than fabricating undocumented mobility/doping/layout differences.

Any secondary changes must be justified by terminal behavior and documented as APM engineering choices.

## 10. Why APM016F multi-Vt is workfunction-dominant

BSIM-CMG explicitly models gate workfunction through `PHIG`. Open predictive multi-Vt FinFET model examples such as ASAP7 show meaningful PHIG changes between Vt flavors, while also showing that real fitted families may differ slightly in secondary transport/SCE parameters.

Therefore a truthful generic model strategy is:

- use PHIG/workfunction as dominant Vt-family control;
- validate observable threshold/Ion/Ioff/SS behavior;
- add only minimal evidence-backed secondary adjustment if required.

Calling the method `workfunction_dominant` is more accurate than claiming real multi-Vt processes differ only by PHIG.

## 11. Why APM016F high-voltage/thick-oxide is deferred

A credible high-voltage FinFET family would require more than threshold shifting: gate stack/EOT, voltage handling, geometry, electrostatics, parasitics, and possibly different compact-model calibration.

The evidence burden is substantially larger than LVT/SVT/HVT. v2 therefore focuses on native IHP/FreePDK gate-stack examples and generic core FinFET Vt families. APM016F high-voltage I/O remains a later release candidate.

## 12. Why Ion/Ioff and SS are added

v1 was analog-characterization-centric: gm/Id, gm/gds, DIBL, Y/capacitance, temperature.

Those remain essential, but multi-Vt families are largely chosen around drive/leakage tradeoffs. Ion/Ioff and subthreshold swing expose that dimension directly.

`log10(Ion/Ioff)` is persisted because HVT Ioff can be extremely small and a linear ratio alone is numerically awkward.

The SS method is intentionally frozen only after native-family curve review so APM does not encode an arbitrary extraction window as universal truth.

## 13. Why there are multiple comparison views

Different family questions require different controls.

Threshold siblings:

- equal bias shows drive/leakage differences directly;
- equal inversion (e.g. gm/Id) shows analog gain/current/capacitance behavior at comparable inversion.

Gate-stack/voltage families:

- native-profile view shows intended family operation;
- common-overlap-bias view separates some voltage-profile effect from intrinsic family difference when a legal common bias can be established.

Cross-process golden comparison remains anchored to one representative family per technology so thick-oxide and Vt-option effects do not contaminate the scaling axis.

## 14. Why Benchmark Process/Mismatch are renamed

v1 Benchmark Process was always synthetic, but the word `process` becomes misleading once APM contains multiple nominal Vt/gate-stack families whose real statistical cross-correlation is unknown.

v2 names are:

- Benchmark Global;
- Benchmark Local;
- Benchmark All.

Benchmark Global means shared synthetic observable stress, not a foundry process-correlation claim.

This wording allows one common technology/polarity latent stress to be mapped through family-specific adapters without pretending that real LV/HV or LVT/SVT/HVT fluctuations are fully correlated.

Upstream/native process/mismatch terminology remains unchanged because it belongs to the source model.

## 15. Why the benchmark latent is shared across families

If each Vt family drew an independent benchmark Global Vth shift, deterministic corners or MC could create arbitrary cross-family movement and make comparisons difficult to interpret.

Sharing one technology/polarity observable latent keeps the synthetic stress comparable; each family-specific adapter still maps that common observable target into the correct raw compact-model handle/sign/sensitivity.

This is a benchmark-design choice, not a physical statistical model.

Future evidence may justify family residual latents; the sample namespace is designed to allow them without changing Family identity.

## 16. Why manifest-driven architecture is now justified

In v1, five explicit kit loaders were simple and appropriate. With 13 families and future sparse options, extending those loaders would create repetitive technology-specific code and make taxonomy changes expensive.

The new abstraction has multiple concrete use cases immediately:

- APM130 two families with asymmetric geometry;
- APM045 four families;
- APM022/APM016F three families each;
- simulator-specific bindings that should not live in semantic manifests.

Therefore manifest-driven catalog data is no longer premature abstraction. A plugin system still would be premature; straightforward dataclasses/TOML/discovery is enough.

## 17. Toolchain continuity rationale

v1 already paid the cost of solving EL9/ngspice/OpenVAF/OSDI setup. Restarting that discovery on every architectural release wastes effort and loses useful operational context.

v2 development should reuse the validated local toolchain and compacted Codex implementation knowledge when still valid.

Release reproducibility remains strict: the final v2 clean clone must prove that the repository can recreate the required environment/artifacts from documented source.

## 18. Scope discipline

v2 intentionally does not expand into every available open-PDK device type.

Deferred/not required:

- RF-specific views/models;
- isolated/DNWELL/layout variants as first-class APM families unless later electrical-model evidence/use requires them;
- ESD/SAB families;
- MOS noise common characterization;
- APM016F high-voltage I/O;
- layout/verification/standard-cell artifacts;
- Virtuoso automation.

The goal is a durable family framework plus a carefully chosen 13-family set, not a mirror of entire PDK catalogs.
