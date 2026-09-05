# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def is_repository(root: Path) -> bool:
    """Recognize the current source distribution, independently of release history."""
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
        return (project["name"] == "analog-process-models"
                and (root / "src/apm/__init__.py").is_file()
                and any((root / "models").glob("*/technology.toml"))
                and (root / "variation/benchmark_v2.toml").is_file())
    except (OSError, ValueError, KeyError):
        return False


def repository_root() -> Path:
    """Return the APM checkout root.

    APM is intentionally a source-tree-oriented distribution because model
    decks and provenance remain normal repository assets.  An explicit root is
    useful for installed/editable entry points and clean-clone tests.
    """

    configured = os.environ.get("APM_REPO_ROOT")
    if configured is not None:
        root = Path(configured).expanduser().resolve()
        if not configured or not is_repository(root):
            raise RuntimeError(f"APM_REPO_ROOT is not an APM checkout: {root}")
        return root

    candidates = (Path.cwd(), Path(__file__).resolve().parents[2])
    for start in candidates:
        for candidate in (start, *start.parents):
            if is_repository(candidate):
                return candidate
    raise RuntimeError(
        "could not locate the APM repository; run from the checkout or set APM_REPO_ROOT"
    )


def state_directory(root: Path | None = None) -> Path:
    configured = os.environ.get("APM_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (root or repository_root()) / ".apm"
