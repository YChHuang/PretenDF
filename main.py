
# Copyright (c) 2026 Yen-Chieh Huang
# SPDX-License-Identifier: MIT

import argparse

from core import analyze, fix_fake_landscape, fix_fake_portrait
from fixtures import generate_fake_landscape, generate_fake_portrait


def main():
    parser = argparse.ArgumentParser(prog="main.py", description="PDF geometry fix toolkit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Print orientation/rotation diagnostics for a PDF")
    p_analyze.add_argument("input", help="Path to the PDF to inspect")

    p_fix_land = sub.add_parser(
        "fix-fake-landscape",
        help="Fix Portrait MediaBox + /Rotate=270 (displays as landscape) and write the result",
    )
    p_fix_land.add_argument("input", help="Path to the broken PDF")
    p_fix_land.add_argument("output", help="Path to write the fixed PDF")

    p_fix_port = sub.add_parser(
        "fix-fake-portrait",
        help="Fix Landscape MediaBox + /Rotate=90 (displays as portrait) and write the result",
    )
    p_fix_port.add_argument("input", help="Path to the broken PDF")
    p_fix_port.add_argument("output", help="Path to write the fixed PDF")

    p_gen_land = sub.add_parser("gen-fake-landscape", help="Generate a fake-landscape test fixture")
    p_gen_land.add_argument("output", help="Path to write the generated PDF")

    p_gen_port = sub.add_parser("gen-fake-portrait", help="Generate a fake-portrait test fixture")
    p_gen_port.add_argument("output", help="Path to write the generated PDF")

    args = parser.parse_args()

    if args.command == "analyze":
        print(analyze(args.input))
    elif args.command == "fix-fake-landscape":
        fix_fake_landscape(args.input, args.output)
    elif args.command == "fix-fake-portrait":
        fix_fake_portrait(args.input, args.output)
    elif args.command == "gen-fake-landscape":
        generate_fake_landscape(args.output)
        print(f"Wrote {args.output}")
    elif args.command == "gen-fake-portrait":
        generate_fake_portrait(args.output)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
