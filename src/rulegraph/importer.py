"""Plain-text rule importer — parse bullet-point rule lists into RuleNodes."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rulegraph.rule import RuleEdge, RuleNode


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def import_from_text(text: str, source: str = "", default_type: str = "mechanic") -> list[RuleNode]:
    """Parse plain text into RuleNodes.

    Each line starting with '- ', '* ', or a number+dot becomes a RuleNode.
    Tags are auto-extracted from [bracket] patterns.
    Rule ID is auto-generated as source + SHA hash of the line text.
    """
    nodes: list[RuleNode] = []
    bullet_pattern = re.compile(r"^(?:[-*]|\d+[.)]) +(.+)$")

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = bullet_pattern.match(line)
        if not m:
            continue
        content = m.group(1).strip()

        # Extract tags from [tag] patterns
        tags = re.findall(r"\[([^\]]+)\]", content)
        # Remove tag annotations from the rule text
        clean_text = re.sub(r"\[[^\]]+\]", "", content).strip()
        if not clean_text:
            continue

        rule_hash = _sha16(content)
        prefix = (source + ".") if source else ""
        rule_id = f"{prefix}{rule_hash}"

        node = RuleNode(
            rule_id=rule_id,
            text=clean_text,
            node_type=default_type,
            tags=tags,
            source=source,
            confidence=1.0,
        )
        nodes.append(node)

    return nodes


def import_from_file(path: Path, source: str = "") -> list[RuleNode]:
    """Read a text file and parse it into RuleNodes."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if not source:
        source = path.stem
    return import_from_text(text, source=source)


_KEYWORD_RELATIONS: list[tuple[str, str]] = [
    (r"\bmodifies\b", "modifies"),
    (r"\bsupersedes\b", "supersedes"),
    (r"\brequires\b", "requires"),
    (r"\bexception\b", "exception-to"),
    (r"\boverrides\b", "supersedes"),
    (r"\bdepends on\b", "requires"),
]


def infer_edges(rules: list[RuleNode]) -> list[RuleEdge]:
    """Heuristically infer edges by looking for keyword references between rules.

    For each rule, scan its text for keywords (modifies, supersedes, requires, exception)
    and cross-reference against other rules whose rule_id or tags appear in the text.
    """
    edges: list[RuleEdge] = []
    # Also index by short hash suffix for easier matching
    short_map: dict[str, RuleNode] = {}
    for r in rules:
        parts = r.rule_id.split(".")
        for part in parts:
            short_map.setdefault(part.lower(), r)

    for source_rule in rules:
        text_lower = source_rule.text.lower()
        for pattern, relation in _KEYWORD_RELATIONS:
            if not re.search(pattern, text_lower):
                continue
            # Look for any other rule whose rule_id or tags are mentioned
            for target_rule in rules:
                if target_rule.rule_id == source_rule.rule_id:
                    continue
                # Check if target rule_id or any tag is mentioned in source text
                mentioned = target_rule.rule_id.lower() in text_lower or any(
                    tag.lower() in text_lower for tag in target_rule.tags
                )
                if mentioned:
                    edge = RuleEdge(
                        source_id=source_rule.rule_id,
                        target_id=target_rule.rule_id,
                        relation=relation,
                    )
                    edges.append(edge)

    return edges
