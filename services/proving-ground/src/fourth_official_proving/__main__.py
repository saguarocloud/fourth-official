"""Run the Proving Ground, or gate a candidate against its baseline.

    python -m fourth_official_proving run --config template --matches 20 --out card.json
    python -m fourth_official_proving gate --candidate cand.json --baseline prod.json

`gate` prints each rule and exits 1 when the candidate is blocked, so CI fails the pull request.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fourth_official_contracts import Scorecard, parse_scorecard
from fourth_official_proving.configurations import CONFIGURATIONS
from fourth_official_proving.gate import gate
from fourth_official_proving.runner import run_benchmark
from fourth_official_proving.scorecard import score
from fourth_official_simulator.benchmark import BENCHMARK_SIZE, benchmark_matches

# Matches CI runs on a pull request; the full benchmark runs nightly (plan §9.3).
SMOKE_MATCHES = 20


def _write(path: Path | None, wire: object) -> None:
    text = json.dumps(wire, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def _run(args: argparse.Namespace) -> None:
    runnable = CONFIGURATIONS[args.config]
    runs = asyncio.run(run_benchmark(benchmark_matches(args.matches), runnable.explainer()))
    card = score(runnable.configuration, runs, generated_at=datetime.now(UTC))
    _write(args.out, card.to_wire())


def _gate(args: argparse.Namespace) -> None:
    def read(path: Path) -> Scorecard:
        return parse_scorecard(json.loads(path.read_text(encoding="utf-8")))

    verdict = gate(read(args.candidate), read(args.baseline))
    for check in verdict.checks:
        mark = "pass" if check.passed else "BLOCK"
        sys.stderr.write(f"{mark:>5}  {check.rule}: {check.detail}\n")
    if args.out is not None:
        _write(args.out, verdict.to_wire())
    if not verdict.allowed:
        sys.stderr.write(f"Release Gate: {verdict.candidate} is blocked.\n")
        raise SystemExit(1)
    sys.stderr.write(f"Release Gate: {verdict.candidate} is allowed.\n")


def _matches(value: str) -> int:
    count = int(value)
    if not 1 <= count <= BENCHMARK_SIZE:
        raise argparse.ArgumentTypeError(f"1-{BENCHMARK_SIZE} matches")
    return count


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="fourth_official_proving", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run a configuration over the benchmark")
    run.add_argument("--config", required=True, choices=sorted(CONFIGURATIONS))
    run.add_argument("--matches", type=_matches, default=SMOKE_MATCHES)
    run.add_argument("--out", type=Path, default=None)
    run.set_defaults(handler=_run)
    check = commands.add_parser("gate", help="gate a candidate scorecard against a baseline")
    check.add_argument("--candidate", type=Path, required=True)
    check.add_argument("--baseline", type=Path, required=True)
    check.add_argument("--out", type=Path, default=None)
    check.set_defaults(handler=_gate)
    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
