from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compare import Filters, compare_records
from .loader import default_data_paths, load_records
from .render import render_json, render_markdown, render_terminal
from .windows import resolve_windows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openclaw-cost-diff",
        description="Compare OpenClaw token usage and API cost across windows, agents, models, and channels.",
    )
    parser.add_argument("--data", action="append", type=Path, help="JSON/JSONL file or directory to read. Can be repeated.")
    parser.add_argument("--last", help="Current relative window, such as 24h, 7d, 4w, 3m, or 1y. Defaults to 7d.")
    parser.add_argument("--prev", help="Previous relative window ending at the current window start. Defaults to same length as --last.")
    parser.add_argument("--from", dest="current_from", help="Current explicit start date/time, UTC if no timezone is given.")
    parser.add_argument("--to", dest="current_to", help="Current explicit end date/time. Defaults to now when --from is used.")
    parser.add_argument("--prev-from", help="Previous explicit start date/time.")
    parser.add_argument("--prev-to", help="Previous explicit end date/time.")
    parser.add_argument("--agent", action="append", default=[], help="Filter current window by agent id. Can be repeated.")
    parser.add_argument("--model", action="append", default=[], help="Filter current window by model. Can be repeated.")
    parser.add_argument("--channel", action="append", default=[], help="Filter current window by channel. Can be repeated.")
    parser.add_argument("--prev-agent", action="append", default=[], help="Filter previous window by agent id. Defaults to --agent.")
    parser.add_argument("--prev-model", action="append", default=[], help="Filter previous window by model. Defaults to --model.")
    parser.add_argument("--prev-channel", action="append", default=[], help="Filter previous window by channel. Defaults to --channel.")
    parser.add_argument("--group-by", choices=("model", "agent", "channel"), action="append", help="Contributor dimension. Can be repeated. Defaults to all.")
    parser.add_argument("--top", type=int, default=5, help="Number of contributors to show per dimension. Defaults to 5.")
    parser.add_argument("--regression-threshold", type=float, default=25.0, help="Percent increase that is flagged as a regression. Defaults to 25.")
    parser.add_argument("--fail-on-cost-increase", nargs="?", const=0.0, type=float, metavar="PERCENT", help="Exit 2 if cost increases by more than this percent. With no value, any increase fails.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--markdown", action="store_true", help="Emit Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.json and args.markdown:
        parser.error("--json and --markdown are mutually exclusive")
    if args.top < 1:
        parser.error("--top must be at least 1")

    try:
        current_window, previous_window = resolve_windows(
            last=args.last,
            previous=args.prev,
            current_from=args.current_from,
            current_to=args.current_to,
            previous_from=args.prev_from,
            previous_to=args.prev_to,
        )
    except ValueError as exc:
        parser.error(str(exc))

    paths = args.data or default_data_paths()
    records = load_records(paths)
    group_by = tuple(args.group_by or ("model", "agent", "channel"))
    current_filters = Filters(tuple(args.agent), tuple(args.model), tuple(args.channel))
    previous_filters = Filters(
        tuple(args.prev_agent or args.agent),
        tuple(args.prev_model or args.model),
        tuple(args.prev_channel or args.channel),
    )

    comparison = compare_records(
        records,
        current_window=current_window,
        previous_window=previous_window,
        current_filters=current_filters,
        previous_filters=previous_filters,
        group_by=group_by,
        top=args.top,
    )

    if args.json:
        output = render_json(comparison)
    elif args.markdown:
        output = render_markdown(comparison, regression_threshold=args.regression_threshold)
    else:
        output = render_terminal(comparison, regression_threshold=args.regression_threshold)
    print(output)

    if _should_fail(comparison.cost_delta.amount, comparison.cost_delta.percent, args.fail_on_cost_increase):
        return 2
    return 0


def _should_fail(amount: float, percent: float | None, threshold: float | None) -> bool:
    if threshold is None or amount <= 0:
        return False
    if percent is None:
        return True
    return percent > threshold


if __name__ == "__main__":
    sys.exit(main())

