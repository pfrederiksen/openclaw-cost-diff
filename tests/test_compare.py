from datetime import datetime, timezone

from openclaw_cost_diff.compare import Filters, compare_records
from openclaw_cost_diff.models import CostRecord, Window


def test_grouping_and_delta_calculations():
    records = [
        CostRecord(datetime(2026, 4, 18, tzinfo=timezone.utc), 100, 50, 1.50, "m1", "main", "analysis"),
        CostRecord(datetime(2026, 4, 17, tzinfo=timezone.utc), 20, 10, 0.25, "m2", "worker", "final"),
        CostRecord(datetime(2026, 4, 10, tzinfo=timezone.utc), 50, 25, 0.50, "m1", "main", "analysis"),
    ]

    comparison = compare_records(
        records,
        current_window=Window("current", datetime(2026, 4, 13, tzinfo=timezone.utc), datetime(2026, 4, 20, tzinfo=timezone.utc)),
        previous_window=Window("previous", datetime(2026, 4, 6, tzinfo=timezone.utc), datetime(2026, 4, 13, tzinfo=timezone.utc)),
        current_filters=Filters(),
        previous_filters=Filters(),
        group_by=("model", "agent", "channel"),
        top=5,
    )

    assert comparison.current.input_tokens == 120
    assert comparison.current.output_tokens == 60
    assert comparison.current.cost == 1.75
    assert comparison.previous.cost == 0.50
    assert comparison.cost_delta.amount == 1.25
    assert comparison.cost_delta.percent == 250.0
    assert comparison.groups["model"][0].key == "m1"


def test_missing_cost_data_counts_as_zero_cost_but_keeps_tokens():
    records = [
        CostRecord(datetime(2026, 4, 18, tzinfo=timezone.utc), 100, 50, None, "m1", "main", "analysis"),
        CostRecord(datetime(2026, 4, 10, tzinfo=timezone.utc), 50, 25, 0.50, "m1", "main", "analysis"),
    ]

    comparison = compare_records(
        records,
        current_window=Window("current", datetime(2026, 4, 13, tzinfo=timezone.utc), datetime(2026, 4, 20, tzinfo=timezone.utc)),
        previous_window=Window("previous", datetime(2026, 4, 6, tzinfo=timezone.utc), datetime(2026, 4, 13, tzinfo=timezone.utc)),
        current_filters=Filters(),
        previous_filters=Filters(),
        group_by=("model",),
        top=5,
    )

    assert comparison.current.input_tokens == 100
    assert comparison.current.cost == 0
    assert comparison.current.missing_cost_records == 1


def test_filters_can_compare_different_agents():
    records = [
        CostRecord(datetime(2026, 4, 18, tzinfo=timezone.utc), 100, 50, 1.00, "m1", "main", "analysis"),
        CostRecord(datetime(2026, 4, 10, tzinfo=timezone.utc), 100, 50, 2.00, "m1", "worker", "analysis"),
    ]

    comparison = compare_records(
        records,
        current_window=Window("current", datetime(2026, 4, 13, tzinfo=timezone.utc), datetime(2026, 4, 20, tzinfo=timezone.utc)),
        previous_window=Window("previous", datetime(2026, 4, 6, tzinfo=timezone.utc), datetime(2026, 4, 13, tzinfo=timezone.utc)),
        current_filters=Filters(agents=("main",)),
        previous_filters=Filters(agents=("worker",)),
        group_by=("agent",),
        top=5,
    )

    assert comparison.current.cost == 1.00
    assert comparison.previous.cost == 2.00
