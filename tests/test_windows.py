from datetime import UTC, datetime

import pytest

from openclaw_cost_diff.windows import parse_duration, resolve_windows


def test_date_window_comparison_from_relative_ranges():
    now = datetime(2026, 4, 20, tzinfo=UTC)

    current, previous = resolve_windows(
        last="7d",
        previous="7d",
        current_from=None,
        current_to=None,
        previous_from=None,
        previous_to=None,
        now=now,
    )

    assert current.start == datetime(2026, 4, 13, tzinfo=UTC)
    assert current.end == now
    assert previous.start == datetime(2026, 4, 6, tzinfo=UTC)
    assert previous.end == datetime(2026, 4, 13, tzinfo=UTC)


def test_explicit_date_ranges():
    current, previous = resolve_windows(
        last=None,
        previous=None,
        current_from="2026-04-10",
        current_to="2026-04-20",
        previous_from="2026-03-31",
        previous_to="2026-04-10",
    )

    assert current.start == datetime(2026, 4, 10, tzinfo=UTC)
    assert current.end == datetime(2026, 4, 20, tzinfo=UTC)
    assert previous.start == datetime(2026, 3, 31, tzinfo=UTC)
    assert previous.end == datetime(2026, 4, 10, tzinfo=UTC)


def test_invalid_duration_is_rejected():
    with pytest.raises(ValueError):
        parse_duration("seven-days")

