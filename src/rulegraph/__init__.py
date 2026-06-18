"""rulegraph — Natural-language rulebook compiler for game arbitration."""

from __future__ import annotations

from importlib.metadata import version as _version

from rulegraph.rule import (
    ArbitrationResult,
    RuleArbiter,
    RuleEdge,
    RuleGraph,
    RuleNode,
    RuleStore,
)

__version__ = _version("rulegraph")

__all__ = [
    "ArbitrationResult",
    "RuleArbiter",
    "RuleEdge",
    "RuleGraph",
    "RuleNode",
    "RuleStore",
]
