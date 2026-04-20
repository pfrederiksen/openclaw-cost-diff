import json
from pathlib import Path

from openclaw_cost_diff.cli import main
from openclaw_cost_diff.loader import load_records


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_loads_jsonl_and_session_json_shapes():
    records = load_records([FIXTURES])

    assert len(records) == 9
    assert sum(record.input_tokens for record in records) == 4400
    assert any(record.cost is None for record in records)
    assert {record.agent for record in records} == {"main", "worker", "live-agent"}


def test_loads_nested_extensionless_agent_session_shape():
    records = load_records([FIXTURES / "agents" / "live-agent" / "sessions" / "transcript"])

    assert len(records) == 1
    record = records[0]
    assert record.timestamp.isoformat() == "2026-04-18T15:00:00+00:00"
    assert record.model == "openai-codex/gpt-5.4"
    assert record.agent == "live-agent"
    assert record.channel == "response.completed"
    assert record.input_tokens == 1200
    assert record.output_tokens == 800
    assert record.cost == 0.0805


def test_numeric_epoch_milliseconds_are_parsed():
    records = load_records([FIXTURES / "agents" / "live-agent" / "sessions" / "numeric-time.jsonl"])

    assert len(records) == 1
    assert records[0].timestamp.isoformat() == "2026-04-18T15:00:00+00:00"
    assert records[0].cost == 0.0123


def test_out_of_range_numeric_time_is_ignored_without_crashing():
    records = load_records([FIXTURES / "agents" / "live-agent" / "sessions" / "ambiguous-time.jsonl"])

    assert len(records) == 1
    assert records[0].timestamp.isoformat() == "2026-04-18T15:01:00+00:00"
    assert records[0].cost == 0.015


def test_cli_json_output(capsys):
    code = main(
        [
            "--data",
            str(FIXTURES),
            "--from",
            "2026-04-13",
            "--to",
            "2026-04-20",
            "--prev-from",
            "2026-04-06",
            "--prev-to",
            "2026-04-13",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"]["current"]["input_tokens"] == 3400
    assert payload["totals"]["previous"]["missing_cost_records"] == 1
    assert payload["groups"]["model"][0]["key"] == "openai-codex/gpt-5.4"


def test_cli_fail_on_cost_increase(capsys):
    code = main(
        [
            "--data",
            str(FIXTURES),
            "--from",
            "2026-04-13",
            "--to",
            "2026-04-20",
            "--prev-from",
            "2026-04-06",
            "--prev-to",
            "2026-04-13",
            "--fail-on-cost-increase",
            "10",
        ]
    )

    assert code == 2
    assert "Regression" in capsys.readouterr().out
