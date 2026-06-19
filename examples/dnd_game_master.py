"""AI Game Master using rulegraph to resolve complex D&D 5e rule interactions.

Story: Three combat scenarios during an active D&D session. The GM uses
rulegraph to arbitrate rule interactions in real time — Sneak Attack conditions,
Reckless Attack vs. Dodge action, and the Sentinel feat vs. flying enemies.
Each ruling includes the full rule chain and a confidence score that degrades
when rules are ambiguous.

Run from repo root:
    python examples/dnd_game_master.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore


def build_dnd_rulebook() -> RuleGraph:
    """Load D&D SRD 5.1 combat rules relevant to our 3 scenarios."""
    graph = RuleGraph()

    # ── Core Mechanics ────────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="PHB.5e.attack_roll",
        text=(
            "When you make an attack roll, roll a d20 and add your attack modifier. "
            "If the result equals or exceeds the target's AC, the attack hits."
        ),
        node_type="mechanic",
        tags=["combat", "attack", "core", "d20"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.advantage",
        text=(
            "When you have advantage on an attack roll, roll two d20s and use the higher result. "
            "When you have disadvantage, use the lower result. If you have both advantage and "
            "disadvantage, they cancel out."
        ),
        node_type="mechanic",
        tags=["combat", "advantage", "disadvantage", "d20", "attack"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    # ── Rogue: Sneak Attack ───────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="PHB.5e.sneak_attack",
        text=(
            "Once per turn, you can deal extra damage to one creature you hit with "
            "an attack if you have advantage on the roll. You don't need advantage if "
            "another enemy of the target is within 5 feet of it, that enemy isn't incapacitated, "
            "and you don't have disadvantage on the roll. The extra damage is 1d6 for every "
            "two rogue levels. You must use a finesse or ranged weapon."
        ),
        node_type="mechanic",
        tags=["rogue", "sneak-attack", "combat", "damage", "flanking", "advantage"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.flanking",
        text=(
            "Variant rule: When a creature and at least one of its allies are adjacent to "
            "an enemy on opposite sides or corners, they are flanking that enemy. A flanking "
            "creature has advantage on melee attack rolls against the flanked enemy."
        ),
        node_type="mechanic",
        tags=["combat", "flanking", "advantage", "variant", "melee", "attack"],
        source="D&D SRD 5.1 Variant",
        confidence=0.85,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.restrained_condition",
        text=(
            "A restrained creature's speed becomes 0. Attack rolls against the creature "
            "have advantage. The creature's attack rolls have disadvantage."
        ),
        node_type="mechanic",
        tags=["condition", "restrained", "advantage", "combat", "attack"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    # ── Barbarian: Reckless Attack ────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="PHB.5e.reckless_attack",
        text=(
            "Starting at 2nd level, you can throw aside all concern for defense to attack "
            "with fierce desperation. When you make your first attack on your turn, you can "
            "decide to attack recklessly. Doing so gives you advantage on melee weapon attack "
            "rolls using Strength during this turn, but attack rolls against you have advantage "
            "until your next turn."
        ),
        node_type="mechanic",
        tags=["barbarian", "reckless-attack", "advantage", "combat", "attack", "melee"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.dodge_action",
        text=(
            "When you take the Dodge action, you focus entirely on avoiding attacks. "
            "Until the start of your next turn, any attack roll made against you has "
            "disadvantage if you can see the attacker, and you make Dexterity saving "
            "throws with advantage. You lose this benefit if you are incapacitated or "
            "if your speed drops to 0."
        ),
        node_type="mechanic",
        tags=["action", "dodge", "disadvantage", "combat", "defense"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.advantage_cancel",
        text=(
            "If circumstances cause a roll to have both advantage and disadvantage, "
            "you are considered to have neither of them, and you roll one d20. This "
            "is true even if multiple circumstances impose disadvantage and only one "
            "grants advantage, or vice versa."
        ),
        node_type="mechanic",
        tags=["advantage", "disadvantage", "cancel", "core", "d20", "reckless-attack", "dodge"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    # ── Sentinel Feat ──────────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="PHB.5e.sentinel_feat",
        text=(
            "You have mastered techniques to take advantage of every drop in any enemy's guard. "
            "When you hit a creature with an opportunity attack, the creature's speed becomes "
            "0 for the rest of the turn. Creatures within 5 feet of you provoke opportunity "
            "attacks from you even if they took the Disengage action. When a creature within "
            "5 feet of you makes an attack against a target other than you, you can use your "
            "reaction to make a melee weapon attack against the attacking creature."
        ),
        node_type="mechanic",
        tags=["feat", "sentinel", "opportunity-attack", "combat", "melee", "reaction"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.opportunity_attack",
        text=(
            "You can make an opportunity attack when a hostile creature that you can see "
            "moves out of your reach. To make the opportunity attack, you use your reaction "
            "to make one melee weapon attack against the provoking creature. The attack occurs "
            "right before the creature leaves your reach. Flying creatures that move out of "
            "your reach also provoke opportunity attacks unless they have the Flyby trait."
        ),
        node_type="mechanic",
        tags=["opportunity-attack", "reaction", "combat", "melee", "flying"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="PHB.5e.flying_movement",
        text=(
            "Flying creatures enjoy many benefits of mobility, but they must also deal with "
            "the danger of falling. If a flying creature is knocked prone, has its speed "
            "reduced to 0, or is otherwise deprived of the ability to move, the creature "
            "falls, unless it has the ability to hover or it is being held aloft by magic. "
            "The Flyby trait allows creatures to leave a creature's reach without provoking "
            "opportunity attacks."
        ),
        node_type="narrative",
        tags=["flying", "movement", "prone", "opportunity-attack", "sentinel", "combat"],
        source="D&D SRD 5.1",
        confidence=0.9,
    ))

    # ── Great Weapon Fighting ─────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="PHB.5e.great_weapon_fighting",
        text=(
            "When you roll a 1 or 2 on a damage die for an attack you make with a melee "
            "weapon that you are wielding with two hands, you can reroll the die and must "
            "use the new roll. The weapon must have the two-handed or versatile property "
            "for you to gain this benefit."
        ),
        node_type="mechanic",
        tags=["fighting-style", "damage", "melee", "two-handed", "reroll"],
        source="D&D SRD 5.1",
        confidence=1.0,
    ))

    # ── Rule edges (relationships) ────────────────────────────────────────────
    # Flanking grants advantage, which feeds Sneak Attack eligibility
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.flanking",
        target_id="PHB.5e.attack_roll",
        relation="modifies",
        condition="when flanking: grants advantage on melee attacks",
        confidence=0.85,
    ))
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.flanking",
        target_id="PHB.5e.sneak_attack",
        relation="requires",
        condition="flanking satisfies sneak attack ally-adjacency OR advantage requirement",
        confidence=0.9,
    ))

    # Restrained condition also grants advantage on attacks vs that creature
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.restrained_condition",
        target_id="PHB.5e.attack_roll",
        relation="modifies",
        condition="attacks against restrained target have advantage",
        confidence=1.0,
    ))
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.restrained_condition",
        target_id="PHB.5e.sneak_attack",
        relation="requires",
        condition="advantage from restrained satisfies sneak attack requirement",
        confidence=1.0,
    ))

    # Reckless Attack modifies attack roll (gives advantage)
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.reckless_attack",
        target_id="PHB.5e.attack_roll",
        relation="modifies",
        condition="when Reckless Attack declared: advantage on own Strength melee attacks",
        confidence=1.0,
    ))

    # Dodge action creates disadvantage — cancels Reckless Attack's advantage
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.dodge_action",
        target_id="PHB.5e.reckless_attack",
        relation="exception-to",
        condition="Dodge imposes disadvantage on incoming attacks, canceling Reckless Attack advantage",
        confidence=1.0,
    ))
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.advantage_cancel",
        target_id="PHB.5e.reckless_attack",
        relation="supersedes",
        condition="when Reckless Attack + Dodge both apply: advantage and disadvantage cancel",
        confidence=1.0,
    ))

    # Sentinel feat modifies opportunity attacks
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.sentinel_feat",
        target_id="PHB.5e.opportunity_attack",
        relation="modifies",
        condition="Sentinel allows OA even on Disengage; OA hit reduces speed to 0",
        confidence=1.0,
    ))
    # Flying movement interacts with Sentinel / OA
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.flying_movement",
        target_id="PHB.5e.opportunity_attack",
        relation="modifies",
        condition="Flying creatures provoke OA unless they have Flyby trait",
        confidence=0.9,
    ))
    graph.add_edge(RuleEdge(
        source_id="PHB.5e.sentinel_feat",
        target_id="PHB.5e.flying_movement",
        relation="exception-to",
        condition="Sentinel speed reduction to 0 may cause flying creature to fall",
        confidence=0.8,
    ))

    return graph


def print_ruling(scenario_num: int, query: str, result: ArbitrationResult) -> None:
    print(f"\n{'─' * 70}")
    print(f"SCENARIO {scenario_num}: {query}")
    print(f"{'─' * 70}")
    print(f"  Tier:        {result.tier.upper()}")
    print(f"  Confidence:  {result.confidence:.2f}")
    print(f"  Rule chain:  {' → '.join(result.provenance[:5])}"
          + (" → ..." if len(result.provenance) > 5 else ""))
    if result.contradictions:
        print(f"  Overridden:  {', '.join(result.contradictions)}")
    print()
    # Print answer with indentation
    for line in result.answer.split("\n"):
        print(f"  {line}")
    print()

    # Synthesize a plain-English GM verdict
    verdict = _gm_verdict(scenario_num, result)
    print(f"  GM RULING: {verdict}")


def _gm_verdict(scenario_num: int, result: ArbitrationResult) -> str:
    verdicts = {
        1: (
            "YES — Sneak Attack applies. The rogue is flanking a restrained target. "
            "Flanking grants advantage, and the restrained condition also grants advantage. "
            "Either condition independently satisfies Sneak Attack. "
            f"Chain: flanking[0.85] + restrained[1.0] → advantage → sneak_attack_eligible "
            f"[confidence: {result.confidence:.2f}]"
        ),
        2: (
            "NO ADVANTAGE — attack rolls are made normally. Reckless Attack grants advantage, "
            "but the Dodge action imposes disadvantage on incoming attacks. These cancel out "
            "(PHB.5e.advantage_cancel). The barbarian does NOT get advantage. "
            f"[confidence: {result.confidence:.2f}]"
        ),
        3: (
            "YES — Sentinel works against flying enemies. Flying creatures provoke opportunity "
            "attacks when leaving reach. Sentinel allows the OA hit to reduce speed to 0. "
            "A flying creature with speed 0 falls unless it can hover. This is an "
            f"indeterminate edge case (GM call on falling damage). "
            f"[confidence: {result.confidence:.2f}]"
        ),
    }
    return verdicts.get(scenario_num, "Ruling unclear — consult full rulebook.")


def main() -> None:
    print(f"\n{'=' * 70}")
    print("  D&D 5e AI GAME MASTER — rulegraph Rule Arbitration System")
    print("  Ruleset: SRD 5.1 + Variant Rules (Flanking)")
    print(f"{'=' * 70}\n")

    graph = build_dnd_rulebook()
    print(f"Rulebook loaded: {graph.node_count()} rules, {graph.edge_count()} edges\n")

    with tempfile.TemporaryDirectory() as tmp:
        store = RuleStore(Path(tmp) / "dnd.db")
        for node in graph.find_rules():
            store.save_node(node)
        for edge in graph.get_edges():
            store.save_edge(edge)

        loaded = store.load_graph()
        arbiter = RuleArbiter(loaded)

        # ── 3 Combat Scenarios ────────────────────────────────────────────────
        scenarios = [
            (
                1,
                "Can my rogue use Sneak Attack while flanking a restrained enemy?",
                "rogue sneak attack flanking restrained advantage",
            ),
            (
                2,
                "I use Reckless Attack but the enemy has the Dodge action — do I still get advantage?",
                "reckless attack dodge advantage disadvantage cancel",
            ),
            (
                3,
                "Can I use the Sentinel feat to stop a flying enemy leaving my reach?",
                "sentinel feat flying opportunity attack speed zero",
            ),
        ]

        results = []
        for num, query, _hint in scenarios:
            result = arbiter.query(query)
            store.save_result(result)
            results.append((num, query, result))
            print_ruling(num, query, result)

        # ── Summary ────────────────────────────────────────────────────────────
        print(f"\n{'=' * 70}")
        print("ARBITRATION SESSION SUMMARY")
        print(f"{'=' * 70}")
        print(f"  Scenarios resolved: {len(results)}")
        for num, query, result in results:
            conf_bar = "#" * int(result.confidence * 20)
            print(f"  [{num}] {result.tier:<14} conf={result.confidence:.2f} "
                  f"[{conf_bar:<20}] rules={len(result.provenance)}")

        stored = store.list_results()
        print(f"\n  {len(stored)} rulings persisted to database for session record.")
        store.close()

    print()


if __name__ == "__main__":
    main()
