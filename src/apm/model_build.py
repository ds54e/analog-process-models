# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .toolchain import Toolchain, resolve_toolchain, run_checked

MODEL_SOURCES = {
    "psp103": Path("models/apm130/vendor/psp103/psp103.va"),
    "psp103-nqs": Path("models/apm130/vendor/psp103/psp103_nqs.va"),
    "bsimcmg-112.1.0": Path("models/apm016f/vendor/bsim-cmg-112.1.0/code/bsimcmg.va"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_manifest(source: Path) -> dict[str, str]:
    return {
        str(path.relative_to(source.parent)): sha256_file(path)
        for path in sorted(source.parent.iterdir())
        if path.is_file()
    }


def _cached_build(toolchain: Toolchain) -> dict[str, Any] | None:
    metadata_path = toolchain.osdi_directory / "build.json"
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("schema") != "apm.model-build.v1":
            return None
        if metadata.get("openvaf_sha256") != sha256_file(toolchain.openvaf):
            return None
        artifacts = {item["model_id"]: item for item in metadata["artifacts"]}
        if set(artifacts) != set(MODEL_SOURCES):
            return None
        for model_id, relative_source in MODEL_SOURCES.items():
            source = toolchain.root / relative_source
            artifact = artifacts[model_id]
            output = toolchain.osdi_directory / f"{model_id}.osdi"
            if Path(artifact["output"]).resolve() != output.resolve():
                return None
            if artifact["source_manifest_sha256"] != _source_manifest(source):
                return None
            if not output.is_file() or artifact["output_sha256"] != sha256_file(output):
                return None
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    metadata["metadata_path"] = str(metadata_path)
    metadata["cache_status"] = "verified_reuse"
    return metadata


def build_models(toolchain: Toolchain | None = None, *, force: bool = True) -> dict[str, Any]:
    selected = toolchain or resolve_toolchain()
    selected.osdi_directory.mkdir(parents=True, exist_ok=True)
    if not force:
        cached = _cached_build(selected)
        if cached is not None:
            return cached
    compiler_version = run_checked(
        [selected.openvaf, "--version"], environment=selected.environment()
    )
    artifacts: list[dict[str, Any]] = []

    for model_id, relative_source in MODEL_SOURCES.items():
        source = selected.root / relative_source
        if not source.is_file():
            raise FileNotFoundError(f"vendored Verilog-A source missing: {source}")
        output = selected.osdi_directory / f"{model_id}.osdi"
        command = [
            selected.openvaf,
            "--target_cpu",
            "generic",
            "-I",
            source.parent,
            "-o",
            output,
            source,
        ]
        result = run_checked(command, environment=selected.environment(), cwd=source.parent)
        artifacts.append(
            {
                "model_id": model_id,
                "source": str(relative_source),
                "source_manifest_sha256": _source_manifest(source),
                "output": str(output),
                "output_sha256": sha256_file(output),
                "command": [str(item) for item in command],
                "compiler_stdout": result.stdout.strip(),
                "compiler_stderr": result.stderr.strip(),
            }
        )

    metadata: dict[str, Any] = {
        "schema": "apm.model-build.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "openvaf_path": str(selected.openvaf),
        "openvaf_sha256": sha256_file(selected.openvaf),
        "openvaf_version_output": compiler_version.stdout.strip(),
        "openvaf_upstream_tag": "v24.0.2mob",
        "openvaf_upstream_commit": "fdf2522b70f42793f64b1c72f0195c96dea0cc19",
        "target_cpu": "generic",
        "artifacts": artifacts,
    }
    metadata_path = selected.osdi_directory / "build.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata["metadata_path"] = str(metadata_path)
    metadata["cache_status"] = "rebuilt"
    return metadata
