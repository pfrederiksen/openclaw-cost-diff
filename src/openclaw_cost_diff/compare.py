from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import CostRecord, Delta, Totals, Window


@dataclass(frozen=True)
class Filters:
    agents: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()

    def matches(self, record: CostRecord) -> bool:
        return (
            (not self.agents or record.agent in self.agents)
            and (not self.models or record.model in self.models)
            and (not self.channels or record.channel in self.channels)
        )


@dataclass
class GroupDiff:
    dimension: str
    key: str
    current: Totals
    previous: Totals

    @property
    def cost_delta(self) -> Delta:
        return Delta(self.current.cost, self.previous.cost)

    @property
    def input_delta(self) -> Delta:
        return Delta(float(self.current.input_tokens), float(self.previous.input_tokens))

    @property
    def output_delta(self) -> Delta:
        return Delta(float(self.current.output_tokens), float(self.previous.output_tokens))


@dataclass
class Comparison:
    current_window: Window
    previous_window: Window
    current: Totals
    previous: Totals
    groups: dict[str, list[GroupDiff]]
    total_records_seen: int

    @property
    def cost_delta(self) -> Delta:
        return Delta(self.current.cost, self.previous.cost)

    @property
    def input_delta(self) -> Delta:
        return Delta(float(self.current.input_tokens), float(self.previous.input_tokens))

    @property
    def output_delta(self) -> Delta:
        return Delta(float(self.current.output_tokens), float(self.previous.output_tokens))


def compare_records(
    records: Iterable[CostRecord],
    *,
    current_window: Window,
    previous_window: Window,
    current_filters: Filters,
    previous_filters: Filters,
    group_by: tuple[str, ...],
    top: int,
) -> Comparison:
    current = Totals()
    previous = Totals()
    current_groups = {dimension: defaultdict(Totals) for dimension in group_by}
    previous_groups = {dimension: defaultdict(Totals) for dimension in group_by}
    seen = 0

    for record in records:
        seen += 1
        if current_window.contains(record.timestamp) and current_filters.matches(record):
            current.add(record)
            for dimension in group_by:
                current_groups[dimension][_group_key(record, dimension)].add(record)
        if previous_window.contains(record.timestamp) and previous_filters.matches(record):
            previous.add(record)
            for dimension in group_by:
                previous_groups[dimension][_group_key(record, dimension)].add(record)

    groups: dict[str, list[GroupDiff]] = {}
    for dimension in group_by:
        keys = set(current_groups[dimension]) | set(previous_groups[dimension])
        diffs = [
            GroupDiff(
                dimension=dimension,
                key=key,
                current=current_groups[dimension][key],
                previous=previous_groups[dimension][key],
            )
            for key in keys
        ]
        diffs.sort(key=lambda item: (abs(item.cost_delta.amount), item.current.cost), reverse=True)
        groups[dimension] = diffs[:top]

    return Comparison(
        current_window=current_window,
        previous_window=previous_window,
        current=current,
        previous=previous,
        groups=groups,
        total_records_seen=seen,
    )


def _group_key(record: CostRecord, dimension: str) -> str:
    if dimension == "model":
        return record.model
    if dimension == "agent":
        return record.agent
    if dimension == "channel":
        return record.channel
    raise ValueError(f"unsupported group dimension {dimension!r}")

