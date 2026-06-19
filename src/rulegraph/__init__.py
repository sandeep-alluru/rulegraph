"""rulegraph — Natural-language rulebook compiler for game arbitration."""

from __future__ import annotations

from importlib.metadata import version as _version

from rulegraph.conflicts import RuleConflict, detect_conflicts, find_cycles
from rulegraph.coverage import CoverageTracker, RuleCoverage
from rulegraph.importer import import_from_file, import_from_text, infer_edges
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
    "CoverageTracker",
    "RuleArbiter",
    "RuleConflict",
    "RuleCoverage",
    "RuleEdge",
    "RuleGraph",
    "RuleNode",
    "RuleStore",
    "detect_conflicts",
    "find_cycles",
    "import_from_file",
    "import_from_text",
    "infer_edges",
]
