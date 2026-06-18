"""Demo: build a small D&D SRD rule graph and arbitrate questions against it.

Run from repo root:
    python examples/demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from rulegraph.report import print_result, print_rules, to_markdown
from rulegraph.rule import RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore


def main() -> None:
    print("rulegraph demo — D&D SRD rule arbitration\n")

    # ── Build the rule graph ──────────────────────────────────────────────────
    graph = RuleGraph()

    # Core PHB rules
    graph.add_node(RuleNode(
        rule_id="PHB.attack_roll",
        text=(
            "When you make an attack roll, roll a d20 and add your attack modifier. "
            "If the result equals or exceeds the target's Armor Class, the attack hits."
        ),
        node_type="mechanic",
        tags=["combat", "attack", "dice"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))
    graph.add_node(RuleNode(
        rule_id="PHB.damage_roll",
        text=(
            "When your attack hits, roll the weapon's damage die and add your ability modifier "
            "to determine the damage dealt to the target."
        ),
        node_type="mechanic",
        tags=["combat", "damage", "dice"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))
    graph.add_node(RuleNode(
        rule_id="PHB.difficult_terrain",
        text=(
            "Every foot of movement in difficult terrain costs 1 extra foot. "
            "This rule applies even if multiple things in a space count as difficult terrain."
        ),
        node_type="narrative",
        tags=["movement", "terrain", "environment"],
        source="D&D SRD 5.1",
        confidence=0.85,
    ))
    graph.add_node(RuleNode(
        rule_id="PHB.critical_hit",
        text=(
            "When you score a critical hit, you get to roll extra dice for the attack's "
            "damage against the target. Roll all of the attack's damage dice twice and add "
            "them together."
        ),
        node_type="mechanic",
        tags=["combat", "attack", "critical", "dice"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    # Unearthed Arcana variant
    graph.add_node(RuleNode(
        rule_id="UA.flanking",
        text=(
            "Variant rule: When a creature and at least one of its allies are adjacent to "
            "an enemy on opposite sides, they have advantage on melee attack rolls against "
            "that creature."
        ),
        node_type="mechanic",
        tags=["combat", "attack", "variant", "flanking"],
        source="Unearthed Arcana",
        confidence=0.7,
    ))

    # Add edges: UA flanking modifies the base attack roll
    graph.add_edge(RuleEdge(
        source_id="UA.flanking",
        target_id="PHB.attack_roll",
        relation="modifies",
        condition="when flanking an enemy with an ally",
        confidence=0.7,
    ))

    print(f"Graph built: {graph.node_count()} rules, {graph.edge_count()} edges\n")

    # ── Persist to a temp DB ──────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        store = RuleStore(Path(tmp) / "demo.db")
        for node in graph.find_rules():
            store.save_node(node)
        for edge in graph.get_edges():
            store.save_edge(edge)

        # Reload from DB to confirm round-trip
        loaded_graph = store.load_graph()
        assert loaded_graph.node_count() == graph.node_count()
        print(f"Persisted and reloaded: {loaded_graph.node_count()} rules\n")

        # ── Arbitrate questions ───────────────────────────────────────────────
        arbiter = RuleArbiter(loaded_graph)

        questions = [
            "How do I make an attack roll?",
            "What happens when I score a critical hit?",
            "What is difficult terrain?",
            "Does flanking give advantage on attack rolls?",
        ]

        results = []
        for question in questions:
            result = arbiter.query(question)
            results.append(result)
            store.save_result(result)
            print_result(result)

        # ── Show stored rules ─────────────────────────────────────────────────
        print("\nAll rules in graph:")
        print_rules(loaded_graph.find_rules(), console=None)

        # ── Generate Markdown report ──────────────────────────────────────────
        md = to_markdown(results)
        print("Markdown report preview (first 300 chars):")
        print(md[:300])
        print("...")

        # ── Verify stored results ─────────────────────────────────────────────
        stored = store.list_results()
        assert len(stored) == len(questions), f"Expected {len(questions)} results, got {len(stored)}"
        print(f"\n{len(stored)} arbitration results persisted successfully.")

        store.close()

    print("\nDemo complete.")


if __name__ == "__main__":
    main()
