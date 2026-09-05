# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Read-only exact-object history. Ordinary simulation never imports old code."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

BASELINE = "25140f57c4c3714f6ab4c9c9df44698ad7732662"
# Digest of the pre-migration identity record; new releases may be appended,
# but observations cannot replace the original v1-v5 anchors.
LEGACY_ANCHOR = "0c1d61802f8656607d932266b7d2bb345b8aff6ff72eea12771c3fbf94c3a319"


class HistoryError(RuntimeError):
    """History unavailable, identity drift, or unsafe export request."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_REPLACE_REF_BASE"):
        env.pop(key, None)
    result = subprocess.run(["git", "--no-replace-objects", *args], cwd=root, env=env,
                            capture_output=True, check=False)
    if result.returncode:
        raise HistoryError("MISSING_HISTORY: " + result.stderr.decode(errors="replace").strip())
    return result.stdout


def git_text(root, *args):
    return git(root, *args).decode().strip()


def require_history(root):
    if not (root / ".git").exists():
        raise HistoryError("MISSING_HISTORY: use a full Git clone or import the documented bundle")
    if Path(git_text(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise HistoryError("WRONG_HISTORY_ROOT")
    if git_text(root, "rev-parse", "--is-shallow-repository") != "false":
        raise HistoryError("MISSING_HISTORY: shallow clone; explicitly fetch --unshallow --tags")
    grafts = Path(git_text(root, "rev-parse", "--git-path", "info/grafts"))
    if not grafts.is_absolute():
        grafts = root / grafts
    if grafts.exists():
        raise HistoryError("GRAFTS_UNSUPPORTED: exact-object audit requires original ancestry")


def load_index(root):
    data = tomllib.loads((root / "releases/index.toml").read_text())
    old = {k: data[k] for k in ("baseline", "legacy")}
    if data.get("schema") != "apm.history-index.v1" or digest(canonical(old)) != LEGACY_ANCHOR:
        raise HistoryError("HISTORY_REGISTRY_DRIFT: original identity anchors changed")
    return data


def entries(root, commit):
    result = {}
    for row in git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if row:
            meta, path = row.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            result[path.decode()] = {"mode": mode, "kind": kind, "blob": blob}
    return result


def inventory(root):
    index = load_index(root)
    raw = (root / index["baseline"]["inventory_path"]).read_bytes()
    if digest(raw) != index["baseline"]["inventory_sha256"]:
        raise HistoryError("MIGRATION_INVENTORY_DRIFT")
    result = json.loads(raw)
    if result["commit"] != BASELINE or not result["artifacts"]:
        raise HistoryError("INVALID_MIGRATION_BASELINE")
    return result


def verify_history(root):
    checks, observations = {}, []
    try:
        require_history(root)
        data = load_index(root)
        inv = inventory(root)
        snapshot_commits = {
            'v6-baseline': BASELINE,
            'v5-preflight': inv['frozen_scopes']['preflight']['authority'],
            'v3-publication': git_text(root, 'log', '-1', '--format=%H', BASELINE, '--',
                                       'validation/evidence/publication_v3.json'),
        }
        checks['supplementary_authorities'] = (
            set(data.get('snapshot', {})) == set(snapshot_commits)
            and all(data['snapshot'][k]['commit'] == v for k, v in snapshot_commits.items()))
        authorities = {r[k]["commit"]: r[k] for r in data["legacy"] for k in ("source", "evidence")}
        authorities[BASELINE] = data["baseline"]
        authorities.update({r['commit']: r for r in data.get('snapshot', {}).values()})
        for release in data["legacy"]:
            tag = release["tag"]
            checks[tag + ".annotated_object"] = (
                git_text(root, "rev-parse", "refs/tags/" + tag) == release["tag_object"]
                and git_text(root, "cat-file", "-t", release["tag_object"]) == "tag")
            checks[tag + ".peeled_commit"] = (
                git_text(root, "rev-parse", release["tag_object"] + "^{commit}")
                == release["source"]["commit"])
        for commit, authority in authorities.items():
            observed = entries(root, commit)
            checks[commit + ".tree_inventory"] = (
                git_text(root, "rev-parse", commit + "^{tree}") == authority["tree"]
                and len(observed) == authority["artifact_count"]
                and digest(canonical(observed)) == authority["inventory_sha256_git"])
            git(root, "merge-base", "--is-ancestor", commit, "HEAD")
            observations.append({"commit": commit, "tree": authority["tree"], "artifacts": len(observed)})
        baseline = entries(root, BASELINE)
        checks["baseline_inventory_complete"] = set(baseline) == {a["path"] for a in inv["artifacts"]}
        checks["baseline_bytes_modes"] = all(
            {k: a[k] for k in ("mode", "kind", "blob")} == baseline[a["path"]]
            and digest(git(root, "cat-file", "blob", a["blob"])) == a["sha256"]
            for a in inv["artifacts"])
        for name, scope in inv["frozen_scopes"].items():
            actual = entries(root, scope["authority"])
            checks["old_selector." + name] = bool(scope["entries"]) and all(
                actual.get(path) == entry for path, entry in scope["entries"].items())
        status = "PASS" if checks and all(checks.values()) else "FAIL"
        return {"schema": "apm.history-verification.v1", "status": status,
                "scope": "historical Git objects and committed evidence; no old numerical requalification",
                "checks": checks, "authorities": observations,
                "raw_evidence": "Ignored runs, downloads, environments and binaries are outside Git/bundle coverage."}
    except (OSError, ValueError, KeyError, HistoryError) as error:
        return {"schema": "apm.history-verification.v1", "status": "NOT_VERIFIED",
                "scope": "historical Git objects", "checks": checks, "error": str(error)}


def worktree_bytes(path):
    return os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()


def worktree_mode(path):
    return "120000" if path.is_symlink() else "100755" if path.stat().st_mode & 0o111 else "100644"


def verify_assets(root):
    """No Git needed: enforce the separately pinned local scientific/notice closure."""
    try:
        inv = inventory(root)
        selected = [a for a in inv["artifacts"] if a["action"] == "retain_exact"]
        failures = []
        for a in selected:
            path = root / a["path"]
            try:
                if digest(worktree_bytes(path)) != a["sha256"] or worktree_mode(path) != a["mode"]:
                    failures.append(a["path"])
            except OSError:
                failures.append(a["path"])
        for prefix in ("models", "variation", "passives", "LICENSES"):
            expected = {a["path"] for a in selected if a["path"].startswith(prefix + "/")}
            actual = {p.relative_to(root).as_posix() for p in (root / prefix).rglob("*")
                      if p.is_file() or p.is_symlink()}
            failures.extend(sorted(actual ^ expected))
        return {"status": "PASS" if selected and not failures else "FAIL",
                "scope": "current local scientific and license assets",
                "compared": len(selected), "mismatches": sorted(set(failures))}
    except (OSError, ValueError, KeyError, HistoryError) as error:
        return {"status": "FAIL", "error": str(error)}


def safe_inventory(items):
    """Validate the entire export before creating files; never traverse a symlink."""
    symlinks = {p for p, e in items.items() if e["mode"] == "120000"}
    for path, entry in items.items():
        parts = PurePosixPath(path).parts
        if (not parts or path.startswith(("/", "\\")) or "\\" in path
                or any(p in (".", "..", ".git") for p in parts)
                or PurePosixPath(path).as_posix() != path
                or entry["kind"] != "blob" or entry["mode"] not in ("100644", "100755", "120000")
                or any(str(p) in symlinks for p in PurePosixPath(path).parents)):
            raise HistoryError("UNSAFE_EXPORT_PATH: " + path)


def export_tree(root, release_id, kind, destination):
    if kind not in ("source", "evidence"):
        raise HistoryError("INVALID_EXPORT_KIND")
    report = verify_history(root)
    if report["status"] != "PASS":
        raise HistoryError("HISTORY_NOT_VERIFIED: " + report.get("error", str(report["checks"])))
    release = next((r for r in load_index(root)["legacy"] if r["tag"] == release_id), None)
    snapshot = load_index(root).get('snapshot', {}).get(release_id)
    if release is None and snapshot and kind == 'source':
        release = {'source': snapshot}
    if release is None:
        raise HistoryError("UNKNOWN_RELEASE")
    destination = Path(os.path.abspath(destination.expanduser()))
    if destination.exists() or destination.is_symlink():
        raise HistoryError("EXPORT_DESTINATION_OCCUPIED: choose a new path")
    if any(p.is_symlink() for p in destination.parents):
        raise HistoryError("EXPORT_SYMLINK_PARENT")
    source = release[kind]
    items = entries(root, source["commit"])
    safe_inventory(items)
    for path, entry in items.items():
        if entry["mode"] == "120000":
            target = git(root, "cat-file", "blob", entry["blob"]).decode()
            resolved = (destination / path).parent / target
            if target.startswith("/") or not Path(os.path.abspath(resolved)).is_relative_to(destination):
                raise HistoryError("EXPORT_SYMLINK_ESCAPE: " + path)
    destination.mkdir(parents=True, exist_ok=False)
    for path, entry in items.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = git(root, "cat-file", "blob", entry["blob"])
        if entry["mode"] == "120000":
            target.symlink_to(os.fsdecode(payload))
        else:
            with target.open("xb") as handle:
                handle.write(payload)
            target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
    verified = verify_export(root, source["commit"], destination)
    if verified["status"] != "PASS":
        raise HistoryError("EXPORT_VERIFICATION_FAILED: " + str(verified))
    return {**verified, "release": release_id, "kind": kind, "destination": str(destination)}


def verify_export(root, commit, destination):
    items = entries(root, commit)
    safe_inventory(items)
    actual = set()
    # os.walk never follows directory symlinks; include them in the inventory.
    for folder, dirs, files in os.walk(destination, followlinks=False):
        for name in files + [n for n in dirs if (Path(folder) / n).is_symlink()]:
            actual.add((Path(folder) / name).relative_to(destination).as_posix())
    failures = sorted(actual ^ set(items))
    for path, entry in items.items():
        file = destination / path
        try:
            if any(p.is_symlink() for p in file.parents if p != destination and p.is_relative_to(destination)):
                raise HistoryError("SYMLINK_IN_RECONSTRUCTION")
            if (worktree_mode(file) != entry["mode"]
                    or worktree_bytes(file) != git(root, "cat-file", "blob", entry["blob"])):
                failures.append(path)
        except (OSError, HistoryError):
            failures.append(path)
    return {"status": "PASS" if items and not failures else "FAIL", "commit": commit,
            "tree": git_text(root, "rev-parse", commit + "^{tree}"),
            "artifact_count": len(items), "mismatches": sorted(set(failures))}
