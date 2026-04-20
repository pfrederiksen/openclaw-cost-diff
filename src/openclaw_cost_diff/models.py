from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CostRecord:
    timestamp: datetime
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None
    model: str = "unknown"
    agent: str = "unknown"
    channel: str = "unknown"
    source: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Window:
    label: str
    start: datetime
    end: datetime

    def contains(self, timestamp: datetime) -> bool:
        return self.start <= timestamp < self.end


@dataclass
class Totals:
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    records: int = 0
    missing_cost_records: int = 0
    sources: set[str] = field(default_factory=set)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, record: CostRecord) -> None:
        self.input_tokens += record.input_tokens
        self.output_tokens += record.output_tokens
        if record.cost is None:
            self.missing_cost_records += 1
        else:
            self.cost += record.cost
        self.records += 1
        if record.source:
            self.sources.add(record.source)


@dataclass(frozen=True)
class Delta:
    current: float
    previous: float

    @property
    def amount(self) -> float:
        return self.current - self.previous

    @property
    def percent(self) -> float | None:
        if self.previous == 0:
            if self.current == 0:
                return 0.0
            return None
        return (self.amount / self.previous) * 100.0

