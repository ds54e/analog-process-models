# Upstream Research Baseline for APM v2

> **Historical record — dated v2 research baseline.** This document records
> research used to implement v2. The listed implementation questions were
> resolved before v2.0.0 and the resulting architecture is preserved by
> v3.0.0. This file is not current status or an active TODO list. See
> `README.md`, `STATUS.md`, and the provenance manifests for current facts.

This file records researched facts that seeded v2 implementation. It is dated
guidance, not immutable policy. Re-check authoritative upstream sources before
new pinning, vendoring, or release claims.

Baseline date: **2026-08-30**

If current primary evidence differs, use the stronger/current evidence and record the material change in `STATUS.md` and provenance.

## 1. v1 validated runtime baseline

The v1.0.0 release already validated the following direct WSL2/EL9 reference path:

- WSL2 kernel / AlmaLinux 9.7 x86_64 on Linux filesystem;
- Python 3.9.25;
- ngspice 47 built with `--enable-predictor --enable-osdi --with-x=no`;
- project-local OpenVAF-ReLoaded tag `v24.0.2mob`, commit `fdf2522b70f42793f64b1c72f0195c96dea0cc19`, source-built against AlmaLinux LLVM 20.1.8;
- PSP103 OSDI real-device execution;
- BSIM-CMG 112.1.0 OSDI real-device execution;
- native ngspice BSIM3/BSIM4 execution.

Implementation implication:

Reuse the existing validated development toolchain when present. Do not repeat bootstrap discovery/build merely because v2 starts. Final v2 release still requires its own clean-clone/bootstrap validation.

## 2. IHP SG13G2 LV/HV family structure

Authoritative upstream:

- https://github.com/IHP-GmbH/IHP-Open-PDK
- pinned v1 APM source revision: `331c00484213b13414777eec1336ef5c29b969bd`

Primary README finding:

IHP SG13G2 provides two gate oxides:

- thin gate oxide for 1.2 V digital logic;
- thick gate oxide for 3.3 V supply.

For both modules, NMOS, PMOS, and isolated NMOS devices are offered.

This supports treating `lv` and `hv` as distinct electrical families while avoiding `core`/`io` as primary family identity.

### LV model evidence

The upstream low-voltage corner model identifies:

- PSP 103.6;
- maximum drain-source voltage 1.5 V in the model header;
- valid L approximately 0.13–10 um;
- valid W approximately 0.15–10 um;
- TT/SS/FF/SF/FS corner structure;
- TT statistical/process and mismatch structures in the open model set.

APM v1 validated LV nominal/corners/statistical/mismatch behavior using the pinned snapshot.

### HV model evidence

The pinned IHP snapshot also contains `cornerMOShv.lib`; no IHP revision bump is inherently required just to add HV.

The inspected HV file identifies:

- PSP 103.6;
- model revision/date information in the file header;
- maximum drain-source voltage 3.3 V;
- NMOS valid L approximately 0.45–10 um;
- PMOS valid L approximately 0.40–10 um;
- W approximately 0.30–10 um;
- TT/SS/FF/SF/FS corner libraries;
- TT statistical profile;
- TT mismatch profile.

The file carries an Apache-2.0 header at current upstream; exact pinned-revision files must still be audited before vendoring.

Implementation implications:

- prefer the existing pinned IHP revision when exact HV assets/terms pass audit;
- support N/P-specific geometry bounds;
- validate LV/HV native variation independently;
- do not invent LV-HV joint correlation or upstream combined `all` semantics;
- isolated/RF/layout variants are not automatically new APM electrical families.

## 3. FreePDK45 family structure

Relevant authoritative/project sources include NCSU FreePDK45 documentation/manual and the already selected open-source-clean FreePDK45 1.4 mirror pinned by APM v1.

v1 APM source revision:

`688ee68ec5301e5fe11ebee5e53c1109d3cfd51d`

FreePDK45 identifies distinct model flavors including:

- VTL — low threshold;
- VTG — general/regular threshold;
- VTH — high threshold;
- THKOX — thick-oxide/high-voltage off-chip-I/O-oriented device.

The FreePDK45 manual uses Ion/Ioff as central Vt-flavor comparison observables. Published manual values show the expected trend from VTL to VTG to VTH: lower Ion and dramatically lower Ioff as threshold rises.

Implementation implications:

- use `vtl`, `vtg`, `vth`, `thkox` as technology-local family identities;
- keep `vtg` as cross-process anchor;
- use VTL/VTG/VTH native behavior to establish v2 family comparison methodology and generic multi-Vt target ranges;
- re-audit every newly vendored VTL/VTH/THKOX file at the exact pinned clean-mirror revision;
- do not assume THKOX nominal/reference VDD from secondary convention alone. If the pinned primary model/docs do not state a clear nominal VDD, choose an APM operating profile explicitly and label its origin `apm_selected`.

## 4. SKY130 evidence for sparse/asymmetric families and validity metadata

Authoritative documentation:

- https://skywater-pdk.readthedocs.io/en/main/rules/device-details.html

Useful structural findings:

- SPICE model validity is documented separately for VDS/VGS/VBS, supporting APM's separation of model validity from Operating Profile.
- SKY130 contains low-/high-/native-threshold device options that are not necessarily symmetric N/P pairs; for example documented high-Vt 1.8 V PMOS and native NMOS options demonstrate that family/device sets may be sparse.
- native NMOS documentation describes creation by blocking VT implants, while threshold-flavor devices can share broad cross-section/gate-stack basis with threshold-adjust process differences.

Implementation implications:

- v2 schema must not require every family to contain N and P;
- validity fields should be optional/evidence-backed rather than treated as unlimited when missing;
- APM022 threshold-isolated generic LVT/HVT variants are a defensible controlled abstraction when clearly labeled, but should not be misrepresented as a complete foundry multi-Vt process recreation.

## 5. GF180 evidence for family versus layout/operating variants

Authoritative documentation:

- https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_15.html

The GF180 device list demonstrates:

- 3.3 V NMOS inside/outside DNWELL can map to the same `nfet_03v3` SPICE model;
- 5 V and 6 V NMOS device options can map to the same `nfet_06v0` electrical model;
- analogous DNWELL/SAB/layout variants may share electrical models;
- native-Vt devices use distinct electrical model identities.

Implementation implications:

- operating-voltage/use/layout variant is not automatically Electrical Family identity;
- DNWELL/isolated/SAB/RF views should not explode the family taxonomy when terminal electrical identity is shared;
- Operating Profile is a separate first-class concept because one electrical model may legitimately be characterized/used under more than one profile;
- reserve future mode/view extension rather than overloading v2 Family.

## 6. BSIM-CMG workfunction semantics and ASAP7 multi-Vt evidence

Authoritative BSIM-CMG model documentation identifies `PHIG` as gate workfunction.

Relevant open predictive example:

- The-OpenROAD-Project ASAP7 PDK/model cards.

ASAP7 documentation provides multiple FinFET Vt flavors (RVT/LVT/SLVT and SRAM flavor). Inspected open model cards show that NMOS LVT/RVT/SLVT share a common broad FinFET geometry/EOT basis while changing `PHIG` materially. The same cards also show smaller family-dependent changes in parameters such as mobility/short-channel/saturation-related terms.

Implementation implications:

- APM016F multi-Vt should be `workfunction_dominant`, not falsely described as `PHIG-only`;
- begin generic LVT/HVT development with PHIG changes calibrated to terminal threshold targets;
- allow only minimal evidence-backed secondary changes if PHIG-only terminal behavior is poor;
- use ASAP7 only as qualitative structural evidence/trend context. Do not copy ASAP7 numerical parameter values into APM016F.

## 7. Generic multi-Vt target strategy

Do not freeze APM022/APM016F LVT/SVT/HVT spacing before native/open family characterization.

Preferred evidence order:

1. APM045 VTL/VTG/VTH terminal characterization using the exact v2 framework;
2. other public/open PDK family behavior such as SKY130;
3. advanced open/predictive examples such as ASAP7;
4. compact-model semantics and public literature.

Use these to choose rounded generic observable targets/trends, not to copy a source model card.

Hard generic family-ordering target:

- `|Vth_LVT| < |Vth_SVT| < |Vth_HVT|`;
- `Ion_LVT > Ion_SVT > Ion_HVT`;
- `Ioff_LVT > Ioff_SVT > Ioff_HVT`.

Do not force universal monotonic DIBL/gain/capacitance ordering without evidence.

## 8. Subthreshold swing methodology

Subthreshold swing is useful/required for multi-Vt family characterization, but the extraction window is not yet sufficiently justified to freeze in this planning phase.

Implementation should evaluate candidate terminal methods on APM130 LV/HV and APM045 VTL/VTG/VTH data, for example local derivative versus one-decade or normalized-current linear-fit approaches, then freeze a robust method with fit diagnostics before release.

Do not move the extraction window silently per device merely to obtain a plausible number.

## 9. Benchmark family correlation interpretation

Real multi-Vt family process correlation is not generally justified by a simple universal coefficient. Do not invent values such as `rho=0.8`.

APM v2 therefore defines Benchmark Global as **common synthetic observable stress**, not a physical foundry process-correlation model:

- draw technology/polarity `vth` and `drive` latent stresses;
- apply the same observable stress to all relevant electrical families in that technology;
- convert it through family/device-specific real-tool calibrated raw adapters.

This preserves comparable benchmark severity and family ordering without claiming real family correlation.

Keep the resolved sample namespace extensible for future family-specific residual latents if evidence eventually supports them.

Upstream/native variation keeps actual upstream semantics and does not inherit APM benchmark correlation assumptions.

## 10. Toolchain/research discipline

Do not redo solved v1 toolchain research without reason. First inventory the actual existing project-local toolchain and compare it with v1 evidence.

When a v2 fact matters to a release claim:

1. re-check primary authoritative source;
2. prefer already pinned v1 source revision when suitable;
3. pin exact new file/revision/hash;
4. distinguish observed upstream evidence from APM inference/engineering choice;
5. record alternate interpretations/unknowns when material;
6. record final decision in provenance/status/evidence;
7. never treat absence of public evidence as proof of a hidden/proprietary property.

## 11. Historical v2 implementation questions (resolved for v2.0.0)

The v2 implementation was required to resolve the following with evidence
before release. Their outcomes are recorded in the v2 tag, provenance files,
and validation evidence; this list is retained to show the original research
boundary:

- exact FreePDK45 VTL/VTH/THKOX imported file set and file-level audit;
- THKOX reference operating profile/VDD;
- common-overlap gate-stack comparison biases;
- final SS extraction convention;
- APM022 generic multi-Vt target spacing;
- APM016F generic multi-Vt target spacing and whether secondary parameters beyond PHIG need changes;
- whether v1 benchmark sigma/corner severity remains appropriate after all 13 family adapters are characterized.
