from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .benchmark import (
    BENCHMARK_CORNERS,
    BENCHMARK_MODES,
    BenchmarkError,
    resolve_corner,
    resolve_monte_carlo,
    write_resolved_sample,
)
from .benchmark_validate import validate_benchmark
from .characterize import CharacterizationError, characterize
from .doctor import run_doctor
from .model_build import build_models
from .toolchain import ToolchainError

TECHNOLOGIES = ("apm350", "apm130", "apm045", "apm022", "apm016f")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apm",
        description="Analog Process Models characterization framework",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Run reference-runtime and compact-model smoke tests")
    sub.add_parser("build-models", help="Build local generated compact-model artifacts")

    p_char = sub.add_parser("characterize", help="Characterize one technology kit")
    p_char.add_argument("technology", choices=TECHNOLOGIES)
    p_char.add_argument(
        "--output",
        type=Path,
        help="Result directory (default: a new UTC-stamped directory below results/<technology>)",
    )

    p_validate = sub.add_parser("validate", help="Run repository validation/regression checks")
    p_validate.add_argument(
        "--release",
        action="store_true",
        help=(
            "Evaluate the v1.0 release-gate contract; required unimplemented, skipped, "
            "or failed automatically-checkable gates must cause a non-zero exit status"
        ),
    )

    p_compare = sub.add_parser("compare", help="Compare two technology kits")
    p_compare.add_argument("technology_a", choices=TECHNOLOGIES)
    p_compare.add_argument("technology_b", choices=TECHNOLOGIES)

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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "build-models":
            result = build_models()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "doctor":
            result = run_doctor()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "characterize":
            result = characterize(args.technology, args.output)
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
        CharacterizationError,
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ToolchainError,
    ) as error:
        print(f"apm {args.command}: {error}", file=sys.stderr)
        return 1
    mode = " --release" if args.command == "validate" and args.release else ""
    parser.error(
        f"'{args.command}{mode}' is part of the v1.0 contract but is not implemented yet; "
        "see GOAL.md and validation/release_gates.toml"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
