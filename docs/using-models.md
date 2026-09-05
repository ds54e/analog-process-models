# Use a model in your circuit

Start at the repository root after [setup](getting-started.md), with a working
ngspice 47 and configured toolchain. Model sources and wrappers are ordinary local
files; using a nominal transistor does not require release qualification.

The public planar terminal order is **d g s b**, with `w,l` in SPICE length units.
For example, `Xdevice d g 0 0 apm045_vtg_nmos w=2u l=0.24u` instantiates a 2 um-wide,
0.24 um-long VTG NMOS with source/body tied to zero. FinFET wrappers instead expose
`l,nfin`, where NFIN is an integer. No common multiplicity/finger API is provided.

The complete [APM045 circuit](../examples/nominal/apm045.cir) includes both the
unchanged nominal FreePDK45 card and the family wrapper. The wrapper alone does
not include its model card. APM045/APM022 use ngspice's native BSIM4; APM350 uses
native BSIM3. The [APM130 circuit](../examples/nominal/apm130.cir) additionally
selects the IHP `mos_tt` library and loads generated PSP103 OSDI modules. APM016F
also needs an OSDI module, compiled from its pinned BSIM-CMG sources.

Execute both complete examples. The subshell working directory is deliberate:
the include paths and output locations in these circuits are relative to
`examples/nominal`. Resolve the configured simulator, create a new output folder,
and build the PSP103 artifacts before running the second example.

<!-- apm-journey: nominal -->
```bash
.venv/bin/apm build-models
apm_ngspice="$(.venv/bin/python -c 'from apm.toolchain import resolve_toolchain; print(resolve_toolchain().ngspice)')"
mkdir .apm/tutorial-nominal
(cd examples/nominal && "$apm_ngspice" -n -b apm045.cir > ../../.apm/tutorial-nominal/apm045.log 2>&1)
(cd examples/nominal && "$apm_ngspice" -n -b apm130.cir > ../../.apm/tutorial-nominal/apm130.log 2>&1)
```

Inspect `.apm/tutorial-nominal/*-idvg.txt` for gate voltage in V and `i(Vd)` in A,
and both logs for successful analyses. Current through the drain supply is negative
for this conducting NMOS; current entering the device drain is its negative. A
zero ngspice exit code alone is insufficient: inspect diagnostics and output rows.

For a different family, inspect its `ngspice/binding.toml` and the output of
`apm describe` for actual include/library sections, public name, geometry and
Operating Profile. The profile selects a study condition; it is not a safe-voltage
rating. Preserve the model's local include closure when organizing your circuit.
These examples establish compact-model execution, not foundry or silicon accuracy.
For automated signed-current, gm/gds and Y-matrix extraction, continue with
[characterization](characterization.md).
