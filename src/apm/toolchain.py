# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .paths import repository_root, state_directory


class ToolchainError(RuntimeError):
    """A required reference-runtime component is unavailable or failed."""


@dataclass(frozen=True)
class Toolchain:
    root: Path
    state: Path
    ngspice: Path
    openvaf: Path
    llvm_library_paths: tuple[Path, ...]

    @property
    def osdi_directory(self) -> Path:
        return self.state / "build" / "osdi"

    def environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        local_libraries = [str(path) for path in self.llvm_library_paths if path.is_dir()]
        existing = environment.get("LD_LIBRARY_PATH")
        if existing:
            local_libraries.append(existing)
        if local_libraries:
            environment["LD_LIBRARY_PATH"] = os.pathsep.join(local_libraries)
        return environment


def _resolve_executable(config_name: str, local: Path, command_name: str) -> Path:
    configured = os.environ.get(config_name)
    if configured:
        path = Path(configured).expanduser().resolve()
    elif local.is_file():
        path = local.resolve()
    else:
        discovered = shutil.which(command_name)
        if not discovered:
            raise ToolchainError(
                f"{command_name} not found; run tools/bootstrap-el9.sh or set {config_name}"
            )
        path = Path(discovered).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ToolchainError(f"configured executable is not executable: {path}")
    return path


def resolve_toolchain(root: Path | None = None) -> Toolchain:
    resolved_root = (root or repository_root()).resolve()
    state = state_directory(resolved_root)
    toolchain_root = (
        Path(os.environ.get("APM_TOOLCHAIN_DIR", str(state / "toolchain"))).expanduser().resolve()
    )
    ngspice = _resolve_executable(
        "APM_NGSPICE",
        toolchain_root / "ngspice-47" / "bin" / "ngspice",
        "ngspice",
    )
    openvaf = _resolve_executable(
        "APM_OPENVAF",
        toolchain_root / "openvaf-v24.0.2mob" / "bin" / "openvaf-r",
        "openvaf-r",
    )
    llvm_root = toolchain_root / "llvm20-root"
    llvm_library_paths = (
        llvm_root / "usr" / "lib64" / "llvm20" / "lib64",
        llvm_root / "usr" / "lib64",
    )
    return Toolchain(resolved_root, state, ngspice, openvaf, llvm_library_paths)


def run_checked(
    command: Sequence[str | Path],
    *,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    rendered = [str(item) for item in command]
    result = subprocess.run(
        rendered,
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ToolchainError(
            f"command failed with exit {result.returncode}: {' '.join(rendered)}\n{detail}"
        )
    return result
