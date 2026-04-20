from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from .models import Window

_DURATION_RE = re.compile(r"^(?P<count>\d+)(?P<unit>[hdwmy])$")


def parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        dt = datetime.fromisoformat(text)
    else:
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_duration(value: str) -> timedelta:
    match = _DURATION_RE.match(value.strip().lower())
    if not match:
        raise ValueError(f"invalid duration {value!r}; use forms like 24h, 7d, 4w, 3m, or 1y")
    count = int(match.group("count"))
    unit = match.group("unit")
    if unit == "h":
        return timedelta(hours=count)
    if unit == "d":
        return timedelta(days=count)
    if unit == "w":
        return timedelta(weeks=count)
    if unit == "m":
        return timedelta(days=30 * count)
    if unit == "y":
        return timedelta(days=365 * count)
    raise ValueError(f"unsupported duration unit {unit!r}")


def resolve_windows(
    *,
    last: str | None,
    previous: str | None,
    current_from: str | None,
    current_to: str | None,
    previous_from: str | None,
    previous_to: str | None,
    now: datetime | None = None,
) -> tuple[Window, Window]:
    now = (now or datetime.now(UTC)).astimezone(UTC)

    if current_from or current_to:
        if not current_from:
            raise ValueError("--from is required when --to is used")
        start = parse_datetime(current_from)
        end = parse_datetime(current_to) if current_to else now
        current = Window("current", start, end)
    else:
        duration = parse_duration(last or "7d")
        current = Window("current", now - duration, now)

    if current.start >= current.end:
        raise ValueError("current window start must be before end")

    if previous_from or previous_to:
        if not (previous_from and previous_to):
            raise ValueError("--prev-from and --prev-to must be used together")
        previous_window = Window("previous", parse_datetime(previous_from), parse_datetime(previous_to))
    else:
        duration = parse_duration(previous) if previous else current.end - current.start
        previous_window = Window("previous", current.start - duration, current.start)

    if previous_window.start >= previous_window.end:
        raise ValueError("previous window start must be before end")

    return current, previous_window

