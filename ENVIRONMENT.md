# Initial Development Environment

This file records the known starting environment for the first unattended implementation run. It is an input to M0, not validation evidence. The agent must verify all reported facts locally before promoting them to validated status.

## User-reported initial state

- Codex CLI is running **directly inside WSL2 on AlmaLinux**.
- The intended architecture is x86_64.
- ngspice is **not currently installed**.
- OpenVAF-ReLoaded is **not currently assumed to be installed**.
- Required PSP103 / BSIM-CMG OSDI build artifacts are **not currently assumed to exist**.
- Spectre/Virtuoso are not part of the validated local v1.0 reference flow.

Do not treat the missing simulator/compiler toolchain as a blocker. Bootstrapping the reproducible reference toolchain is part of **M0 Runtime qualification**.

## M0 bootstrap objective

Starting from this AlmaLinux environment, establish and document a reproducible toolchain that can perform the required real-device smoke tests.

Initial target:

- WSL2 + AlmaLinux 9 x86_64
- Python >= 3.9
- **ngspice 47 with OSDI support**
- OpenVAF-ReLoaded for Verilog-A -> OSDI compilation where required

The agent must inspect the actual system first (`/etc/os-release`, architecture, installed packages, compiler/tool versions) rather than blindly running installation commands.

## ngspice policy

ngspice 47 is the intended v1.0 reference release. Linux upstream distribution does not need to provide a prebuilt current package; a reproducible source build is acceptable and expected if the distro package is absent, stale, or lacks the required OSDI capability.

Authoritative ngspice OSDI documentation states that an OSDI-capable build should explicitly include:

- `--enable-predictor`
- `--enable-osdi`

If building ngspice from source:

- use an authoritative ngspice 47 source release;
- determine and document the build prerequisites actually needed on AlmaLinux 9;
- use the required OSDI/predictor configuration explicitly rather than assuming distro/default flags;
- prefer a user-local or project-controlled prefix when practical rather than destructively replacing unrelated system software;
- record source release/hash, configure flags, compiler versions, prefix, and `ngspice --version` output in M0 evidence;
- prove OSDI by loading and simulating a real OSDI compact model, not only by checking build flags or shared-library presence.

For hermetic APM runs, prefer batch execution that does not depend on user startup state. In particular, use ngspice's no-user-startup behavior where appropriate (for example the `-n` command-line option) and do not require `~/.spiceinit`.

For model loading, prefer netlist-local `pre_osdi` where practical. Upstream ngspice documents that a relative path passed to `pre_osdi` is resolved relative to the netlist, which is useful for self-contained run directories.

Do not silently downgrade to an older ngspice merely because it is easier to install.

## OpenVAF-ReLoaded policy

OpenVAF-ReLoaded is an external development tool, not a vendored APM runtime payload.

Use an authoritative upstream release/revision and pin the version/revision used for v1.0 validation. Current upstream supports OSDI 0.4 and documents compatibility with ngspice >=44; verify the selected revision against ngspice 47 in M0 rather than relying only on documentation.

Prefer a reproducible installation method. A maintained upstream 64-bit Linux binary may be used if suitable and its provenance/version can be pinned; building from source is also acceptable when needed. If building from source, document the Rust/LLVM requirements actually used on AlmaLinux.

Do not modify user shell startup files merely to make the tool discoverable. Project scripts/configuration may set PATH or explicit tool paths in a reproducible way.

## M0 acceptance evidence

M0 is not complete until the environment is verified and the following actually execute:

1. native BSIM3 device smoke simulation;
2. PSP103 compiled/loaded through OSDI and simulated;
3. native BSIM4 device smoke simulation;
4. BSIM-CMG compiled/loaded through OSDI and simulated as a genuine FinFET device.

Evidence should include exact commands, versions, exit codes, and concise sanity results. Static inspection is not enough.

After M0, update `STATUS.md` with the actual validated environment rather than leaving this initial report as the source of truth.
