from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .compare import Comparison, GroupDiff
from .models import Delta, Totals, Window

SPARK = "▁▂▃▄▅▆▇█"


def render_terminal(comparison: Comparison, *, regression_threshold: float) -> str:
    lines = [
        "OpenClaw cost diff",
        f"Current:  {_format_window(comparison.current_window)}",
        f"Previous: {_format_window(comparison.previous_window)}",
        "",
        _summary_table(comparison, markdown=False),
    ]
    warning = _warning(comparison.cost_delta, regression_threshold)
    if warning:
        lines.extend(["", warning])
    if comparison.current.missing_cost_records or comparison.previous.missing_cost_records:
        lines.extend(
            [
                "",
                "Note: records with missing cost data are included in token totals but treated as $0.00 for cost.",
            ]
        )

    lines.append("")
    lines.append(f"Cost sparkline: {_sparkline(comparison.previous.cost, comparison.current.cost)}")

    for dimension, groups in comparison.groups.items():
        if not groups:
            continue
        lines.extend(["", f"Top contributors by {dimension}:"])
        for group in groups:
            lines.append(_group_line(group))
    return "\n".join(lines)


def render_markdown(comparison: Comparison, *, regression_threshold: float) -> str:
    lines = [
        "# OpenClaw Cost Diff",
        "",
        f"- Current: `{_format_window(comparison.current_window)}`",
        f"- Previous: `{_format_window(comparison.previous_window)}`",
        "",
        _summary_table(comparison, markdown=True),
    ]
    warning = _warning(comparison.cost_delta, regression_threshold)
    if warning:
        lines.extend(["", f"**{warning}**"])
    if comparison.current.missing_cost_records or comparison.previous.missing_cost_records:
        lines.extend(
            [
                "",
                "> Records with missing cost data are included in token totals but treated as `$0.00` for cost.",
            ]
        )
    for dimension, groups in comparison.groups.items():
        if not groups:
            continue
        lines.extend(["", f"## Top Contributors By {dimension.title()}", ""])
        lines.append("| Key | Current cost | Previous cost | Delta | Delta % | Current tokens |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for group in groups:
            lines.append(
                f"| `{group.key}` | {_money(group.current.cost)} | {_money(group.previous.cost)} | "
                f"{_signed_money(group.cost_delta.amount)} | {_percent(group.cost_delta.percent)} | "
                f"{group.current.total_tokens:,} |"
            )
    return "\n".join(lines)


def render_json(comparison: Comparison) -> str:
    return json.dumps(_comparison_to_dict(comparison), indent=2, sort_keys=True)


def _summary_table(comparison: Comparison, *, markdown: bool) -> str:
    rows = [
        ("Input tokens", f"{comparison.current.input_tokens:,}", f"{comparison.previous.input_tokens:,}", _signed_int(comparison.input_delta.amount), _percent(comparison.input_delta.percent)),
        ("Output tokens", f"{comparison.current.output_tokens:,}", f"{comparison.previous.output_tokens:,}", _signed_int(comparison.output_delta.amount), _percent(comparison.output_delta.percent)),
        ("Cost", _money(comparison.current.cost), _money(comparison.previous.cost), _signed_money(comparison.cost_delta.amount), _percent(comparison.cost_delta.percent)),
    ]
    if markdown:
        lines = ["| Metric | Current | Previous | Delta | Delta % |", "| --- | ---: | ---: | ---: | ---: |"]
        lines.extend(f"| {name} | {current} | {previous} | {delta} | {pct} |" for name, current, previous, delta, pct in rows)
        return "\n".join(lines)

    widths = [13, 14, 14, 14, 10]
    header = f"{'Metric':<{widths[0]}} {'Current':>{widths[1]}} {'Previous':>{widths[2]}} {'Delta':>{widths[3]}} {'Delta %':>{widths[4]}}"
    sep = f"{'-' * widths[0]} {'-' * widths[1]} {'-' * widths[2]} {'-' * widths[3]} {'-' * widths[4]}"
    body = [
        f"{name:<{widths[0]}} {current:>{widths[1]}} {previous:>{widths[2]}} {delta:>{widths[3]}} {pct:>{widths[4]}}"
        for name, current, previous, delta, pct in rows
    ]
    return "\n".join([header, sep, *body])


def _group_line(group: GroupDiff) -> str:
    return (
        f"- {group.key}: {_money(group.current.cost)} current vs {_money(group.previous.cost)} previous "
        f"({_signed_money(group.cost_delta.amount)}, {_percent(group.cost_delta.percent)}), "
        f"{group.current.total_tokens:,} current tokens vs {group.previous.total_tokens:,} previous tokens"
    )


def _warning(delta: Delta, threshold: float) -> str | None:
    if delta.amount <= 0:
        return None
    if delta.percent is None:
        return f"Regression: cost increased by {_signed_money(delta.amount)} from a zero-cost baseline."
    if delta.percent >= threshold:
        return f"Regression: cost increased by {_signed_money(delta.amount)} ({_percent(delta.percent)})."
    return None


def _sparkline(previous: float, current: float) -> str:
    values = [previous, current]
    high = max(values)
    if high <= 0:
        return SPARK[0] * 2
    return "".join(SPARK[min(len(SPARK) - 1, int((value / high) * (len(SPARK) - 1)))] for value in values)


def _comparison_to_dict(comparison: Comparison) -> dict[str, Any]:
    return {
        "windows": {
            "current": _window_to_dict(comparison.current_window),
            "previous": _window_to_dict(comparison.previous_window),
        },
        "totals": {
            "current": _totals_to_dict(comparison.current),
            "previous": _totals_to_dict(comparison.previous),
            "delta": {
                "input_tokens": comparison.input_delta.amount,
                "input_tokens_percent": comparison.input_delta.percent,
                "output_tokens": comparison.output_delta.amount,
                "output_tokens_percent": comparison.output_delta.percent,
                "cost": comparison.cost_delta.amount,
                "cost_percent": comparison.cost_delta.percent,
            },
        },
        "groups": {
            dimension: [
                {
                    "key": group.key,
                    "current": _totals_to_dict(group.current),
                    "previous": _totals_to_dict(group.previous),
                    "delta": {
                        "cost": group.cost_delta.amount,
                        "cost_percent": group.cost_delta.percent,
                        "input_tokens": group.input_delta.amount,
                        "input_tokens_percent": group.input_delta.percent,
                        "output_tokens": group.output_delta.amount,
                        "output_tokens_percent": group.output_delta.percent,
                    },
                }
                for group in groups
            ]
            for dimension, groups in comparison.groups.items()
        },
        "records_seen": comparison.total_records_seen,
    }


def _window_to_dict(window: Window) -> dict[str, str]:
    return {"start": _iso(window.start), "end": _iso(window.end)}


def _totals_to_dict(totals: Totals) -> dict[str, Any]:
    return {
        "input_tokens": totals.input_tokens,
        "output_tokens": totals.output_tokens,
        "total_tokens": totals.total_tokens,
        "cost": totals.cost,
        "records": totals.records,
        "missing_cost_records": totals.missing_cost_records,
    }


def _format_window(window: Window) -> str:
    return f"{_iso(window.start)} to {_iso(window.end)}"


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _money(value: float) -> str:
    return f"${value:,.4f}"


def _signed_money(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.4f}"


def _signed_int(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{int(value):,}"


def _percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"
