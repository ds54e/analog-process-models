from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apm",
        description="Analog Process Models characterization framework",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check the reference runtime and model smoke tests")
    sub.add_parser("build-models", help="Build local generated compact-model artifacts")

    p_char = sub.add_parser("characterize", help="Characterize one technology kit")
    p_char.add_argument("technology")

    sub.add_parser("validate", help="Run repository validation and regression checks")

    p_compare = sub.add_parser("compare", help="Compare two technology kits")
    p_compare.add_argument("technology_a")
    p_compare.add_argument("technology_b")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    parser.error(
        f"'{args.command}' is part of the v1.0 contract but is not implemented yet; see GOAL.md"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
