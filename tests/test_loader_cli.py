import json
from pathlib import Path

from openclaw_cost_diff.cli import main
from openclaw_cost_diff.loader import load_records


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_loads_jsonl_and_session_json_shapes():
    records = load_records([FIXTURES])

    assert len(records) == 6
    assert sum(record.input_tokens for record in records) == 2500
    assert any(record.cost is None for record in records)
    assert {record.agent for record in records} == {"main", "worker"}


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
    assert payload["totals"]["current"]["input_tokens"] == 1500
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

