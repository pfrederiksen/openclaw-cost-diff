# openclaw-cost-diff

Compare OpenClaw token usage and API cost across two time windows, agents, models, or channels.

The goal is a small, decision-friendly CLI: what changed, by how much, and which model, agent, or channel contributed most.

## Install

```bash
pipx install openclaw-cost-diff
```

For local development:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Examples

```bash
openclaw-cost-diff --last 7d --prev 7d
openclaw-cost-diff --agent main --last 30d --json
openclaw-cost-diff --model openai-codex/gpt-5.4 --last 14d --prev 14d
openclaw-cost-diff --from 2026-04-01 --to 2026-04-15 --prev-from 2026-03-17 --prev-to 2026-04-01
openclaw-cost-diff --channel analysis --last 7d --markdown
openclaw-cost-diff --last 7d --top 10 --fail-on-cost-increase 25
```

Compare different filter sets by applying `--prev-agent`, `--prev-model`, or `--prev-channel`:

```bash
openclaw-cost-diff --agent main --prev-agent worker --last 7d --prev 7d
```

Read a specific fixture or exported transcript directory:

```bash
openclaw-cost-diff --data ./fixtures --last 30d
openclaw-cost-diff --data ~/.openclaw/sessions --data ~/.openclaw/transcripts --last 7d
```

## Data Discovery

By default the CLI scans:

- `~/.openclaw/sessions`
- `~/.openclaw/transcripts`
- `~/.openclaw`

Set `OPENCLAW_DATA_DIR` to override the defaults. Multiple paths can be separated with your platform path separator, or you can pass repeated `--data` arguments.

The loader accepts `.json`, `.jsonl`, and `.ndjson` files. It supports flat records, arrays, `sessions`, `records`, and common nested transcript containers such as `events`, `messages`, `turns`, `requests`, and `usage`.

## Cost Field Assumptions

`openclaw-cost-diff` intentionally avoids pricing tables. It compares cost data that is already present in local OpenClaw records.

Recognized timestamp fields:

- `timestamp`
- `created_at`
- `started_at`
- `ended_at`
- `time`
- `date`

Recognized token fields:

- Input: `input_tokens`, `prompt_tokens`, `tokens_in`, `input`
- Output: `output_tokens`, `completion_tokens`, `tokens_out`, `output`

Recognized cost fields:

- `cost`
- `cost_usd`
- `total_cost`
- `total_cost_usd`
- `api_cost`
- `api_cost_usd`
- nested `cost.usd`
- nested `cost.amount`

Recognized dimensions:

- Model: `model`, `model_id`, `provider_model`
- Agent: `agent`, `agent_id`, `agentId`, `session_agent`
- Channel: `channel`, `role`, `stream`, `conversation_channel`

Records with missing cost are included in token totals and counted as missing cost records, but they contribute `$0.00` to cost totals.

## Output

Default terminal output includes:

- total input tokens
- total output tokens
- total cost
- delta amount and percent
- top contributors by model, agent, and channel
- a small cost sparkline
- regression warnings when cost jumps beyond `--regression-threshold`

Machine-readable JSON is available with `--json`. Markdown is available with `--markdown`.

## Limitations

- This tool is a cost comparison utility, not a full observability system.
- It does not infer costs from model pricing tables.
- Month and year relative durations are approximate: `1m` is 30 days and `1y` is 365 days.
- Unknown or unsupported transcript shapes may need export normalization before analysis.
- Naive datetimes are treated as UTC.

## Release

Tags matching `v*` run the release workflow:

1. Run tests.
2. Build the Python package.
3. Publish to PyPI using `PYPI_API_TOKEN` or PyPI trusted publishing.
4. Create a GitHub release.
5. Bump the Homebrew formula in `pfrederiksen/homebrew-tap` using `HOMEBREW_TAP_TOKEN`.

Do not commit PyPI tokens. Store release credentials as GitHub Actions secrets or use PyPI trusted publishing.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
openclaw-cost-diff --data fixtures --from 2026-04-13 --to 2026-04-20 --prev-from 2026-04-06 --prev-to 2026-04-13
```

