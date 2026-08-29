# SPDX-FileCopyrightText: APM contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from pathlib import Path


def repository_root() -> Path:
    """Return the APM checkout root.

    APM is intentionally a source-tree-oriented v1 distribution because model
    decks and provenance remain normal repository assets.  An explicit root is
    useful for installed/editable entry points and clean-clone tests.
    """

    configured = os.environ.get("APM_REPO_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
        if not (root / "validation" / "release_gates.toml").is_file():
            raise RuntimeError(f"APM_REPO_ROOT is not an APM checkout: {root}")
        return root

    candidates = (Path.cwd(), Path(__file__).resolve().parents[2])
    for start in candidates:
        for candidate in (start, *start.parents):
            if (candidate / "validation" / "release_gates.toml").is_file():
                return candidate
    raise RuntimeError(
        "could not locate the APM repository; run from the checkout or set APM_REPO_ROOT"
    )


def state_directory(root: Path | None = None) -> Path:
    configured = os.environ.get("APM_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (root or repository_root()) / ".apm"
