"""Coverage tracking — measure which rules are queried during arbitration."""

from __future__ import annotations

from dataclasses import dataclass

from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleGraph


@dataclass
class RuleCoverage:
    total_rules: int
    rules_queried: int
    rules_never_queried: int
    coverage_pct: float
    most_used_rules: list[tuple[str, int]]   # (rule_id, query_count)
    dead_rules: list[str]

    def to_dict(self) -> dict:
        return {
            "total_rules": self.total_rules,
            "rules_queried": self.rules_queried,
            "rules_never_queried": self.rules_never_queried,
            "coverage_pct": self.coverage_pct,
            "most_used_rules": self.most_used_rules,
            "dead_rules": self.dead_rules,
        }


class CoverageTracker:
    """Wraps a RuleArbiter to track which rules are invoked."""

    def __init__(self, arbiter: RuleArbiter) -> None:
        self._arbiter = arbiter
        self._query_counts: dict[str, int] = {}

    def arbitrate(self, query: str) -> ArbitrationResult:
        """Delegate to arbiter and record which rules were used."""
        result = self._arbiter.query(query)
        for rule_id in result.provenance:
            self._query_counts[rule_id] = self._query_counts.get(rule_id, 0) + 1
        return result

    def report(self) -> RuleCoverage:
        """Generate a coverage report."""
        graph: RuleGraph = self._arbiter.graph
        all_rule_ids = set(graph._nodes.keys())
        total = len(all_rule_ids)
        queried_ids = set(self._query_counts.keys())
        never_queried_ids = all_rule_ids - queried_ids
        rules_queried = len(queried_ids & all_rule_ids)
        coverage_pct = (rules_queried / total * 100.0) if total > 0 else 0.0

        sorted_used = sorted(
            [(rid, count) for rid, count in self._query_counts.items() if rid in all_rule_ids],
            key=lambda x: x[1],
            reverse=True,
        )

        return RuleCoverage(
            total_rules=total,
            rules_queried=rules_queried,
            rules_never_queried=len(never_queried_ids),
            coverage_pct=round(coverage_pct, 2),
            most_used_rules=sorted_used[:10],
            dead_rules=sorted(never_queried_ids),
        )

    def reset(self) -> None:
        """Reset query counts."""
        self._query_counts.clear()
