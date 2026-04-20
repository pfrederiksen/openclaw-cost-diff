from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CostRecord
from .windows import parse_datetime

DEFAULT_DATA_DIRS = (
    "~/.openclaw/agents",
    "~/.openclaw/sessions",
    "~/.openclaw/transcripts",
    "~/.openclaw",
)

TEXT_SUFFIXES = {".json", ".jsonl", ".ndjson", ".log", ".txt", ""}
CONTAINER_KEYS = ("events", "messages", "turns", "requests", "records", "sessions")
NESTED_MAPPING_KEYS = ("usage", "response", "payload", "message", "data", "result", "cost", "metrics")
TIMESTAMP_KEYS = ("timestamp", "created_at", "createdAt", "started_at", "startedAt", "ended_at", "endedAt", "time", "date", "ts")
MIN_REASONABLE_TIMESTAMP = datetime(2000, 1, 1, tzinfo=timezone.utc)
MAX_REASONABLE_TIMESTAMP = datetime(2100, 1, 1, tzinfo=timezone.utc)
INPUT_KEYS = ("input_tokens", "inputTokens", "prompt_tokens", "promptTokens", "tokens_in", "tokensIn", "input")
OUTPUT_KEYS = ("output_tokens", "outputTokens", "completion_tokens", "completionTokens", "tokens_out", "tokensOut", "output")
MODEL_KEYS = ("model", "model_id", "modelId", "provider_model", "providerModel")
AGENT_KEYS = ("agent", "agent_id", "agentId", "session_agent", "sessionAgent")
CHANNEL_KEYS = ("channel", "role", "stream", "conversation_channel", "conversationChannel", "type")
COST_KEYS = (
    "cost",
    "cost_usd",
    "costUsd",
    "costUSD",
    "total_cost",
    "totalCost",
    "total_cost_usd",
    "totalCostUsd",
    "totalCostUSD",
    "api_cost",
    "apiCost",
    "api_cost_usd",
    "apiCostUsd",
    "apiCostUSD",
)


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
        if _looks_parseable(path):
            yield path
        return
    for child in path.rglob("*"):
        if child.is_file() and _looks_parseable(child):
            yield child


def _load_file(path: Path) -> Iterator[CostRecord]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if not text.strip():
        return

    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            yield from _load_json_lines(text, path)
            return
        yield from _records_from_payload(payload, str(path))
        return

    yield from _load_json_lines(text, path)


def _load_json_lines(text: str, path: Path) -> Iterator[CostRecord]:
    parsed_any = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_any = True
        yield from _records_from_payload(payload, f"{path}:{line_number}")

    if parsed_any:
        return

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return
    yield from _records_from_payload(payload, str(path))


def _records_from_payload(payload: Any, source: str, context: Mapping[str, Any] | None = None) -> Iterator[CostRecord]:
    context = context or {}
    if isinstance(payload, list):
        for item in payload:
            yield from _records_from_payload(item, source, context)
        return

    if not isinstance(payload, Mapping):
        return

    inherited = {**context, **_context_from_mapping(payload)}

    if _has_container_list(payload):
        for child in _iter_children(payload):
            yield from _records_from_payload(child, source, inherited)
        return

    record = _record_from_mapping(payload, source, inherited)
    if record is not None:
        yield record
        return

    for child in _iter_children(payload):
        yield from _records_from_payload(child, source, inherited)


def _record_from_mapping(item: Mapping[str, Any], source: str, context: Mapping[str, Any]) -> CostRecord | None:
    timestamp = _timestamp(item) or _timestamp(context)
    if timestamp is None:
        return None

    usage = _find_usage_mapping(item)
    cost_block = _find_cost_mapping(item)
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
        cost = _float_from(cost_block, COST_KEYS + ("usd", "amount", "total"))
    if cost is None and usage:
        cost = _float_from(usage, COST_KEYS)

    if input_tokens == 0 and output_tokens == 0 and cost is None:
        return None

    return CostRecord(
        timestamp=timestamp,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        model=_string_from(item, MODEL_KEYS)
        or _find_nested_string(item, MODEL_KEYS)
        or _string_from(context, MODEL_KEYS)
        or "unknown",
        agent=_string_from(item, AGENT_KEYS)
        or _find_nested_string(item, AGENT_KEYS)
        or _string_from(context, AGENT_KEYS)
        or _agent_from_source(source)
        or "unknown",
        channel=_string_from(item, CHANNEL_KEYS)
        or _find_nested_string(item, CHANNEL_KEYS)
        or _string_from(context, CHANNEL_KEYS)
        or "unknown",
        source=source,
    )


def _timestamp(item: Mapping[str, Any]) -> datetime | None:
    value = _first_value(item, TIMESTAMP_KEYS)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _datetime_from_epoch(value)
    if isinstance(value, str):
        try:
            return parse_datetime(value)
        except ValueError:
            return None
    return None


def _datetime_from_epoch(value: int | float) -> datetime | None:
    if isinstance(value, bool) or value <= 0:
        return None

    candidates = [float(value)]
    if value >= 1_000_000_000_000_000_000:
        candidates.insert(0, float(value) / 1_000_000_000)
    if value >= 1_000_000_000_000_000:
        candidates.insert(0, float(value) / 1_000_000)
    if value >= 100_000_000_000:
        candidates.insert(0, float(value) / 1_000)

    for seconds in candidates:
        try:
            timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            continue
        if MIN_REASONABLE_TIMESTAMP <= timestamp < MAX_REASONABLE_TIMESTAMP:
            return timestamp
    return None


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _looks_parseable(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _has_container_list(item: Mapping[str, Any]) -> bool:
    return any(isinstance(item.get(key), list) for key in CONTAINER_KEYS)


def _iter_children(item: Mapping[str, Any]) -> Iterator[Any]:
    for value in item.values():
        if isinstance(value, Mapping):
            yield value
        elif isinstance(value, list):
            yield from value


def _context_from_mapping(item: Mapping[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in TIMESTAMP_KEYS + MODEL_KEYS + AGENT_KEYS + CHANNEL_KEYS:
        if key in item and _is_scalar(item[key]):
            context[key] = item[key]
    return context


def _find_usage_mapping(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = _mapping(item.get("usage"))
    if direct is not None:
        return direct
    return _find_nested_mapping(item, lambda value: _has_any_key(value, INPUT_KEYS + OUTPUT_KEYS))


def _find_cost_mapping(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = _mapping(item.get("cost"))
    if direct is not None:
        return direct
    return _find_nested_mapping(item, lambda value: _has_any_key(value, COST_KEYS + ("usd", "amount", "total")))


def _find_nested_mapping(item: Mapping[str, Any], predicate: Any) -> Mapping[str, Any] | None:
    stack = [_mapping(item.get(key)) for key in NESTED_MAPPING_KEYS]
    while stack:
        candidate = stack.pop(0)
        if candidate is None:
            continue
        if predicate(candidate):
            return candidate
        for key in NESTED_MAPPING_KEYS:
            child = _mapping(candidate.get(key))
            if child is not None:
                stack.append(child)
    return None


def _find_nested_string(item: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    mapping = _find_nested_mapping(item, lambda value: _has_any_key(value, keys))
    if mapping is None:
        return None
    return _string_from(mapping, keys)


def _has_any_key(item: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in item for key in keys)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _agent_from_source(source: str) -> str | None:
    parts = Path(source.split(":", 1)[0]).parts
    for index, part in enumerate(parts):
        if part == "agents" and index + 1 < len(parts):
            return parts[index + 1]
    return None


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
