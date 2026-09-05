from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

from . import __version__
from .benchmark import (
    BENCHMARK_CORNERS,
    BENCHMARK_MODES,
    BenchmarkError,
    resolve_corner,
    resolve_monte_carlo,
    write_resolved_sample,
)
from .benchmark_validate import validate_benchmark
from .catalog import CatalogError, DeviceSpec, FamilySpec, TechnologySpec, load_catalog
from .characterize import CharacterizationError, characterize_selector
from .compare import (
    ComparisonError,
    compare_anchors,
    compare_families,
    compare_set,
    validate_all_characterizations,
)
from .doctor import run_doctor
from .lifecycle import ValidationError as ReleaseValidationError
from .maintenance_validate import validate_maintenance_repository
from .model_build import build_models
from .native_variation import NativeVariationError, validate_apm130_native
from .noise import NoiseCharacterizationError, characterize_noise_selector
from .noise_catalog import NoiseCatalogError, validate_noise_catalog
from .noise_method_validate import NoiseMethodValidationError, validate_noise_method
from .noise_validate import NoiseValidationError, validate_noise_spike
from .paths import repository_root
from .provenance_validate import ProvenanceValidationError, validate_provenance
from .research_numerics import ResearchError
from .spectre_validate import SpectreStructureError, validate_spectre
from .toolchain import ToolchainError


def _jsonable(value: object) -> object:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apm",
        description="Analog Process Models characterization framework",
    )
    parser.add_argument("--version", action="version", version=f"APM {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Run reference-runtime and compact-model smoke tests")
    sub.add_parser("build-models", help="Build local generated compact-model artifacts")

    p_research = sub.add_parser("research", help="Source-aware local research variation")
    research_sub = p_research.add_subparsers(dest="research_command", required=True)
    research_sub.add_parser("describe", help="Show approved profiles and support boundaries")
    rp = research_sub.add_parser("sample", help="Persist a UID-keyed reference realization")
    rp.add_argument("--profile", type=Path, required=True)
    rp.add_argument("--request", type=Path, required=True)
    rp.add_argument("--seed", type=int, required=True)
    rp.add_argument("--index", type=int, required=True)
    rp.add_argument("--state", type=Path, required=True)
    rp.add_argument("--output", type=Path, required=True)
    rp.add_argument("--allow-artificial", action="store_true")
    rr = research_sub.add_parser("run", help="Run or replay a saved realization")
    rr.add_argument("--request", type=Path, required=True)
    rr.add_argument("--realization", type=Path, required=True)
    rr.add_argument("--output", type=Path, required=True)
    rr.add_argument("--temperature-c", type=float, default=26.85)
    rc = research_sub.add_parser("check", help="Execute the preserved Research numerical methodology on current code")
    rc.add_argument("--output", type=Path, required=True)
    rc.add_argument("--suite", choices=("sampler", "mapping", "statistics", "circuits", "replay", "io", "all"), default="all")

    p_history = sub.add_parser("history", help="List, verify or export exact historical source/evidence")
    hs = p_history.add_subparsers(dest="history_command", required=True)
    hs.add_parser("list")
    hv = hs.add_parser("verify")
    hv.add_argument("--output", type=Path)
    he = hs.add_parser("export")
    he.add_argument("release")
    he.add_argument("kind", choices=("source", "evidence"))
    he.add_argument("--output", type=Path, required=True)

    p_list = sub.add_parser("list", help="List manifest-discovered catalog entities")
    p_list.add_argument("kind", choices=("technologies", "families", "devices"))
    p_list.add_argument("selector", nargs="?")

    p_describe = sub.add_parser("describe", help="Describe a technology/family/device selector")
    p_describe.add_argument("selector")

    p_char = sub.add_parser("characterize", help="Characterize a technology/family/device selector")
    p_char.add_argument("selector")
    p_char.add_argument(
        "--profile",
        help="Operating-profile ID (default: the family manifest's release profile)",
    )
    p_char.add_argument(
        "--output",
        type=Path,
        help="Result directory (default: a new UTC-stamped directory below results/<technology>)",
    )

    p_validate = sub.add_parser("validate", help="Run repository validation/regression checks")
    release_mode = p_validate.add_mutually_exclusive_group()
    release_mode.add_argument(
        "--release",
        action="store_true",
        help=(
            "Historical v3 workflow migration diagnostic; use its exact source for "
            "immutable-release reproducibility"
        ),
    )
    release_mode.add_argument(
        "--release-v4",
        choices=("candidate", "exact-tag"),
        metavar="PHASE",
        help=(
            "Historical v4 migration diagnostic; reproduce the original contract "
            "from an attested fresh clone"
        ),
    )
    release_mode.add_argument(
        "--release-v5",
        choices=("candidate",),
        metavar="PHASE",
        help="Historical v5 migration diagnostic; use its exact source",
    )
    release_mode.add_argument("--qualify", choices=("candidate", "exact-tag"),
                              help="Execute the current release campaign; never create tags/releases")
    p_validate.add_argument("--scope", choices=("current", "product"), default="current",
                            help="Product omits Git/history and maintainer tool checks explicitly")
    p_validate.add_argument("--approval-file", type=Path,
                            help="External approved candidate and existing tag identity, exact-tag only")
    p_validate.add_argument(
        "--output",
        type=Path,
        help="Validation evidence directory (default: a new UTC-stamped directory under .apm)",
    )

    p_compare = sub.add_parser("compare", help="Compare two technology or family selectors")
    p_compare.add_argument("selector_a")
    p_compare.add_argument("selector_b")
    p_compare.add_argument(
        "--output",
        type=Path,
        help="Result directory (default: a new UTC-stamped comparison directory)",
    )

    p_compare_set = sub.add_parser(
        "compare-set", help="Run a manifest-defined within-technology comparison set"
    )
    p_compare_set.add_argument("technology")
    p_compare_set.add_argument("set_id")
    p_compare_set.add_argument("--output", type=Path, required=True)

    p_compare_anchors = sub.add_parser(
        "compare-anchors", help="Compare the five manifest-selected cross-process anchors"
    )
    p_compare_anchors.add_argument("--output", type=Path, required=True)

    p_characterization = sub.add_parser(
        "characterization-check",
        help="Run and audit terminal characterization across all 15 electrical families",
    )
    p_characterization.add_argument("--output", type=Path, required=True)

    p_sample = sub.add_parser(
        "sample-variation", help="Resolve a deterministic APM benchmark Monte Carlo sample"
    )
    p_sample.add_argument("--request", type=Path, required=True)
    p_sample.add_argument("--mode", choices=BENCHMARK_MODES, required=True)
    p_sample.add_argument("--seed", type=int, required=True)
    p_sample.add_argument("--output", type=Path, required=True)

    p_corner = sub.add_parser(
        "resolve-corner", help="Resolve a deterministic APM benchmark corner vector"
    )
    p_corner.add_argument("corner", choices=BENCHMARK_CORNERS)
    p_corner.add_argument("--request", type=Path, required=True)
    p_corner.add_argument("--output", type=Path, required=True)

    p_benchmark = sub.add_parser(
        "benchmark-check",
        help="Run deterministic real-ngspice benchmark variation/passive validation",
    )
    p_benchmark.add_argument("--output", type=Path, required=True)

    p_native = sub.add_parser(
        "apm130-native-check",
        help="Run selected IHP-native corner, process, and mismatch validation",
    )
    p_native.add_argument("--output", type=Path, required=True)

    p_spectre = sub.add_parser(
        "spectre-check",
        help="Audit experimental/unverified model-only Spectre artifacts structurally",
    )
    p_spectre.add_argument("--output", type=Path, required=True)

    p_provenance = sub.add_parser(
        "provenance-check",
        help="Audit exact model provenance, licensing, and self-contained distribution",
    )
    p_provenance.add_argument("--output", type=Path, required=True)

    p_noise = sub.add_parser(
        "noise", help="Run stationary small-signal noise characterization for one public device"
    )
    p_noise.add_argument("selector")
    p_noise.add_argument(
        "--profile",
        help="Operating-profile ID (default: the family manifest's default profile)",
    )
    p_noise.add_argument("--output", type=Path, required=True)

    p_noise_check = sub.add_parser(
        "noise-check",
        help="Qualify the analytic noise harness and run the V3-N0 four-engine spike",
    )
    p_noise_check.add_argument("--output", type=Path, required=True)

    p_noise_method_check = sub.add_parser(
        "noise-method-check",
        help="Run the complete V3-N1 noise acquisition and fit-method qualification",
    )
    p_noise_method_check.add_argument("--output", type=Path, required=True)

    p_noise_catalog_check = sub.add_parser(
        "noise-catalog-check",
        help="Run or strictly resume the live-catalog stationary-noise qualification",
    )
    p_noise_catalog_check.add_argument("--output", type=Path, required=True)
    p_noise_catalog_check.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only completed results whose request and bound artifact hashes validate",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "history":
            from .history import export_tree, load_index, verify_history
            root = repository_root()
            if args.history_command == "list":
                result = {"status": "INDEX_ONLY", "releases": load_index(root)["legacy"],
                          "note": "Listing local locators is not history verification."}
            elif args.history_command == "export":
                result = export_tree(root, args.release, args.kind, args.output)
            else:
                result = verify_history(root)
                if args.output:
                    from .lifecycle import write_report
                    if args.output.exists():
                        raise ReleaseValidationError("HISTORY_REPORT_DESTINATION_OCCUPIED")
                    write_report(args.output, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1 if result["status"] in ("FAIL", "NOT_VERIFIED") else 0
        if args.command == "list":
            catalog = load_catalog(repository_root())
            if args.kind == "technologies":
                if args.selector is not None:
                    raise CatalogError("list technologies does not take a selector")
                result = [item.technology_id for item in catalog.technologies]
            elif args.kind == "families":
                if args.selector is None:
                    raise CatalogError("list families requires a technology selector")
                result = [item.family_id for item in catalog.technology(args.selector).families]
            else:
                if args.selector is None:
                    raise CatalogError("list devices requires a technology/family selector")
                resolved = catalog.resolve(args.selector)
                if not isinstance(resolved, FamilySpec):
                    raise CatalogError("list devices selector must resolve to a family")
                result = [item.device_id for item in resolved.devices]
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "describe":
            resolved = load_catalog(repository_root()).resolve(args.selector)
            if not isinstance(resolved, (TechnologySpec, FamilySpec, DeviceSpec)):
                raise CatalogError("selector did not resolve to a catalog entity")
            print(json.dumps(_jsonable(resolved), indent=2, sort_keys=True))
            return 0
        if args.command == "build-models":
            result = build_models()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "research":
            from .research_cli import research_command
            result = research_command(args)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("status") not in ("FAIL", "FAILED", "BLOCKED") else 1
        if args.command == "doctor":
            result = run_doctor()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "validate":
            if args.release or args.release_v4 or args.release_v5:
                from .history import load_index
                tag = "v3.0.0" if args.release else "v4.0.0" if args.release_v4 else "v5.0.0"
                record = next(r for r in load_index(repository_root())["legacy"] if r["tag"] == tag)
                raise ReleaseValidationError(
                    f"HISTORICAL_WORKFLOW_MOVED: {tag} qualification belongs to exact source "
                    f"{record['source']['commit']}. Use apm history export {tag} source --output "
                    f"<new-directory> and its preserved procedure. See docs/history.md.")
            if args.qualify:
                if args.scope != "current":
                    raise ReleaseValidationError("RELEASE_REQUIRES_CURRENT_SCOPE")
                from .release import qualify_release
                if args.approval_file and args.qualify != "exact-tag":
                    raise ReleaseValidationError("APPROVAL_ONLY_FOR_EXACT_TAG")
                approval = json.loads(args.approval_file.read_text()) if args.approval_file else None
                result = qualify_release(args.output, phase=args.qualify, approval=approval)
            else:
                if args.approval_file:
                    raise ReleaseValidationError("APPROVAL_ONLY_FOR_EXACT_TAG")
                result = validate_maintenance_repository(args.output, scope=args.scope)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "characterize":
            result = characterize_selector(
                args.selector, args.output, operating_profile_id=args.profile
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "benchmark-check":
            result = validate_benchmark(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "checks": result["checks"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "apm130-native-check":
            result = validate_apm130_native(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "selected_upstream_profiles": result["selected_upstream_profiles"],
                        "checks": result["checks"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "spectre-check":
            result = validate_spectre(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "backend_status": result["backend_status"],
                        "real_tool_validation_performed": result["real_tool_validation_performed"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "checks": result["checks"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "provenance-check":
            result = validate_provenance(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "checks": result["checks"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "noise":
            result = characterize_noise_selector(
                args.selector,
                args.output,
                operating_profile_id=args.profile,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "noise-check":
            result = validate_noise_spike(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "milestone": result["milestone"],
                        "acceptance_result": result["acceptance_result"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "report_sha256": result["report_sha256"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "noise-method-check":
            result = validate_noise_method(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "milestone": result["milestone"],
                        "acceptance_result": result["acceptance_result"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "report_sha256": result["report_sha256"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "noise-catalog-check":
            result = validate_noise_catalog(
                args.output,
                resume=args.resume,
                progress=lambda message: print(message, file=sys.stderr, flush=True),
            )
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "milestone": result["milestone"],
                        "acceptance_result": result["acceptance_result"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "report_sha256": result["report_sha256"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "characterization-check":
            result = validate_all_characterizations(args.output)
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "checks": result["checks"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "compare":
            result = compare_families(
                args.selector_a,
                args.selector_b,
                args.output,
            )
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "selectors": result["selectors"],
                        "output_directory": result["output_directory"],
                        "report_path": result["report_path"],
                        "checks": result["checks"],
                        "relations": result["relations"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "compare-set":
            result = compare_set(args.technology, args.set_id, args.output)
            print(json.dumps(_jsonable(result), indent=2, sort_keys=True))
            return 0
        if args.command == "compare-anchors":
            result = compare_anchors(args.output)
            print(json.dumps(_jsonable(result), indent=2, sort_keys=True))
            return 0
        if args.command in ("sample-variation", "resolve-corner"):
            request = json.loads(args.request.read_text(encoding="utf-8"))
            if args.command == "sample-variation":
                result = resolve_monte_carlo(request, mode=args.mode, seed=args.seed)
            else:
                result = resolve_corner(request, corner=args.corner)
            output = write_resolved_sample(result, args.output)
            print(
                json.dumps(
                    {
                        "sample_id": result["sample_id"],
                        "variation_mode": result["variation_mode"],
                        "corner_profile": result["corner_profile"],
                        "output": str(output),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
    except (
        BenchmarkError,
        CatalogError,
        CharacterizationError,
        ComparisonError,
        FileNotFoundError,
        json.JSONDecodeError,
        NativeVariationError,
        NoiseCharacterizationError,
        NoiseCatalogError,
        NoiseMethodValidationError,
        NoiseValidationError,
        OSError,
        ProvenanceValidationError,
        ReleaseValidationError,
        RuntimeError,
        SpectreStructureError,
        ToolchainError,
        ResearchError,
    ) as error:
        print(f"apm {args.command}: {error}", file=sys.stderr)
        return 1
    parser.error(f"unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
