from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import CostRecord
from .windows import parse_datetime

DEFAULT_DATA_DIRS = (
    "~/.openclaw/sessions",
    "~/.openclaw/transcripts",
    "~/.openclaw",
)

TIMESTAMP_KEYS = ("timestamp", "created_at", "started_at", "ended_at", "time", "date")
INPUT_KEYS = ("input_tokens", "prompt_tokens", "tokens_in", "input")
OUTPUT_KEYS = ("output_tokens", "completion_tokens", "tokens_out", "output")
COST_KEYS = ("cost", "cost_usd", "total_cost", "total_cost_usd", "api_cost", "api_cost_usd")


def default_data_paths() -> list[Path]:
    configured = os.environ.get("OPENCLAW_DATA_DIR")
    values = configured.split(os.pathsep) if configured else DEFAULT_DATA_DIRS
    return [Path(value).expanduser() for value in values]


def load_records(paths: Iterable[Path]) -> list[CostRecord]:
    records: list[CostRecord] = []
    for path in paths:
        if not path.exists():
            continue
        for file_path in _iter_files(path):
            records.extend(_load_file(file_path))
    return records


def _iter_files(path: Path) -> Iterator[Path]:
    if path.is_file():
        if path.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
            yield path
        return
    for child in path.rglob("*"):
        if child.is_file() and child.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
            yield child


def _load_file(path: Path) -> Iterator[CostRecord]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if not text.strip():
        return

    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield from _records_from_payload(payload, f"{path}:{line_number}")
        return

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return
    yield from _records_from_payload(payload, str(path))


def _records_from_payload(payload: Any, source: str) -> Iterator[CostRecord]:
    if isinstance(payload, list):
        for item in payload:
            yield from _records_from_payload(item, source)
        return

    if not isinstance(payload, Mapping):
        return

    if "sessions" in payload and isinstance(payload["sessions"], list):
        for session in payload["sessions"]:
            yield from _records_from_payload(session, source)
        return

    if "records" in payload and isinstance(payload["records"], list):
        for record in payload["records"]:
            yield from _records_from_payload(record, source)
        return

    session_context = payload
    nested = _first_list(payload, ("events", "messages", "turns", "requests", "usage"))
    if nested is not None:
        for item in nested:
            if isinstance(item, Mapping):
                merged = {**session_context, **item}
                yield from _record_from_mapping(merged, source)
        return

    yield from _record_from_mapping(payload, source)


def _record_from_mapping(item: Mapping[str, Any], source: str) -> Iterator[CostRecord]:
    timestamp = _timestamp(item)
    if timestamp is None:
        return

    usage = _mapping(item.get("usage"))
    cost_block = _mapping(item.get("cost"))
    input_tokens = _int_from(item, INPUT_KEYS)
    output_tokens = _int_from(item, OUTPUT_KEYS)

    if usage:
        input_tokens = input_tokens or _int_from(usage, INPUT_KEYS)
        output_tokens = output_tokens or _int_from(usage, OUTPUT_KEYS)
        if not input_tokens and "tokens" in usage and isinstance(usage["tokens"], Mapping):
            input_tokens = _int_from(usage["tokens"], INPUT_KEYS)
            output_tokens = output_tokens or _int_from(usage["tokens"], OUTPUT_KEYS)

    cost = _float_from(item, COST_KEYS)
    if cost is None and cost_block:
        cost = _float_from(cost_block, COST_KEYS + ("usd", "amount"))
    if cost is None and usage:
        cost = _float_from(usage, COST_KEYS)

    if input_tokens == 0 and output_tokens == 0 and cost is None:
        return

    yield CostRecord(
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        model=_string_from(item, ("model", "model_id", "provider_model")) or "unknown",
        agent=_string_from(item, ("agent", "agent_id", "agentId", "session_agent")) or "unknown",
        channel=_string_from(item, ("channel", "role", "stream", "conversation_channel")) or "unknown",
        source=source,
    )


def _timestamp(item: Mapping[str, Any]) -> datetime | None:
    value = _first_value(item, TIMESTAMP_KEYS)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).astimezone()
    if isinstance(value, str):
        try:
            return parse_datetime(value)
        except ValueError:
            return None
    return None


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _first_list(item: Mapping[str, Any], keys: tuple[str, ...]) -> list[Any] | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, list):
            return value
    return None


def _first_value(item: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _int_from(item: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    value = _first_value(item, keys)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_from(item: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    value = _first_value(item, keys)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_from(item: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    value = _first_value(item, keys)
    if value in (None, ""):
        return None
    return str(value)

