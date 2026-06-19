"""Rule conflict detection — find contradictions and cycles in a RuleGraph."""

from __future__ import annotations

from dataclasses import dataclass

from rulegraph.rule import RuleGraph


@dataclass
class RuleConflict:
    rule_a_id: str
    rule_b_id: str
    conflict_type: str   # "direct_contradiction", "circular_dependency", "overlapping_scope"
    description: str
    severity: str        # "critical", "warning", "info"

    def to_dict(self) -> dict:
        return {
            "rule_a_id": self.rule_a_id,
            "rule_b_id": self.rule_b_id,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "severity": self.severity,
        }


def detect_conflicts(graph: RuleGraph) -> list[RuleConflict]:
    """Find rules that may contradict or circularly depend on each other."""
    conflicts: list[RuleConflict] = []

    # 1. Circular dependencies
    cycles = find_cycles(graph)
    seen_cycle_pairs: set[frozenset[str]] = set()
    for cycle in cycles:
        for i in range(len(cycle)):
            a = cycle[i]
            b = cycle[(i + 1) % len(cycle)]
            pair = frozenset([a, b])
            if pair not in seen_cycle_pairs:
                seen_cycle_pairs.add(pair)
                conflicts.append(RuleConflict(
                    rule_a_id=a,
                    rule_b_id=b,
                    conflict_type="circular_dependency",
                    description=f"Circular dependency detected: {' -> '.join([*cycle, cycle[0]])}",
                    severity="critical",
                ))

    # 2. Direct contradictions — rules that both supersede each other
    edges = graph.get_edges()
    supersedes_map: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation in ("supersedes", "exception-to"):
            supersedes_map.setdefault(edge.source_id, set()).add(edge.target_id)

    rule_ids = graph.node_ids()
    for i, a in enumerate(rule_ids):
        for b in rule_ids[i + 1:]:
            a_supersedes_b = b in supersedes_map.get(a, set())
            b_supersedes_a = a in supersedes_map.get(b, set())
            if a_supersedes_b and b_supersedes_a:
                conflicts.append(RuleConflict(
                    rule_a_id=a,
                    rule_b_id=b,
                    conflict_type="direct_contradiction",
                    description=f"Rules '{a}' and '{b}' mutually supersede each other.",
                    severity="critical",
                ))

    # 3. Overlapping scope — same tags + different node_type
    nodes = graph.nodes()
    for i, a_node in enumerate(nodes):
        for b_node in nodes[i + 1:]:
            if a_node.node_type != b_node.node_type:
                shared_tags = set(a_node.tags) & set(b_node.tags)
                if shared_tags:
                    conflicts.append(RuleConflict(
                        rule_a_id=a_node.rule_id,
                        rule_b_id=b_node.rule_id,
                        conflict_type="overlapping_scope",
                        description=(
                            f"Rules '{a_node.rule_id}' ({a_node.node_type}) and "
                            f"'{b_node.rule_id}' ({b_node.node_type}) share tags: "
                            f"{', '.join(sorted(shared_tags))}"
                        ),
                        severity="warning",
                    ))

    return conflicts


def find_cycles(graph: RuleGraph) -> list[list[str]]:
    """Find circular dependencies in the rule graph using DFS."""
    # Build adjacency: only 'requires' edges form dependencies
    adj: dict[str, list[str]] = {rid: [] for rid in graph.node_ids()}
    for edge in graph.get_edges():
        if edge.relation == "requires":
            adj.setdefault(edge.source_id, []).append(edge.target_id)

    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:])
        path.pop()
        rec_stack.discard(node)

    for rule_id in graph.node_ids():
        if rule_id not in visited:
            dfs(rule_id, [])

    return cycles
