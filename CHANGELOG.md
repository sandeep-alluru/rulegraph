# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `RuleConflict` dataclass, `detect_conflicts()` for finding direct contradictions, circular dependencies, and overlapping scope
- `find_cycles()` for detecting circular `requires` dependencies in the rule graph using DFS
- `import_from_text()` and `import_from_file()` for parsing plain bullet-point rule lists into `RuleNode` objects
- Auto-extraction of tags from `[bracket]` patterns and auto-generation of content-addressed rule IDs
- `infer_edges()` for heuristically inferring rule relationships from keywords (modifies, supersedes, requires, exception)
- `RuleCoverage` dataclass and `CoverageTracker` for tracking which rules appear in arbitration results
- CLI commands: `rulegraph conflicts` and `rulegraph coverage [queries...]`
- Tests: `tests/test_conflicts.py`, `tests/test_importer.py`, `tests/test_coverage.py`

## [0.1.0] - 2026-06-17

### Added
- Initial release

[Unreleased]: https://github.com/sandeep-alluru/rulegraph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/rulegraph/releases/tag/v0.1.0
