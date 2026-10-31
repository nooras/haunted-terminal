import argparse
import sys

from haunted_terminal.core import run_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="haunted",
        description="Run a command with an occasional whisper from Gemma.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    run_parser = subparsers.add_parser(
        "run",
        help="run exactly the command you provide",
    )
    run_parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command and arguments (place -- before the command)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("haunted: provide a command after `run --`.", file=sys.stderr)
        return 2
    return run_command(command)
