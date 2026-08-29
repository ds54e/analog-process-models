from __future__ import annotations

import argparse


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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    mode = " --release" if args.command == "validate" and args.release else ""
    parser.error(
        f"'{args.command}{mode}' is part of the v1.0 contract but is not implemented yet; "
        "see GOAL.md and validation/release_gates.toml"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
