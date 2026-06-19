"""Command-line interface for rulegraph."""

from __future__ import annotations

import click

from rulegraph.report import print_result, print_rules, to_json
from rulegraph.rule import RuleArbiter, RuleEdge, RuleNode, RuleStore


def _store(ctx: click.Context) -> RuleStore:
    """Return a RuleStore from the context or default path."""
    db_path = ctx.obj.get("db") if ctx.obj else ".rulegraph/rules.db"
    return RuleStore(db_path)


@click.group()
@click.version_option(package_name="rulegraph")
@click.option(
    "--db",
    default=".rulegraph/rules.db",
    show_default=True,
    help="Path to the rulegraph database.",
    envvar="RULEGRAPH_DB",
)
@click.pass_context
def main(ctx: click.Context, db: str) -> None:
    """Natural-language rulebook compiler for game arbitration.

    rulegraph lets you load game rules into a typed graph and then arbitrate
    questions with deterministic provenance.
    """
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@main.command("add-rule")
@click.argument("rule_id")
@click.argument("text")
@click.option("--type", "node_type", default="mechanic", show_default=True, help="Node type.")
@click.option("--tag", "tags", multiple=True, metavar="TAG", help="Tag (repeat for multiple).")
@click.option("--source", default="", help="Source book or document.")
@click.option("--confidence", type=float, default=1.0, show_default=True)
@click.pass_context
def add_rule(
    ctx: click.Context,
    rule_id: str,
    text: str,
    node_type: str,
    tags: tuple[str, ...],
    source: str,
    confidence: float,
) -> None:
    """Add a rule node to the graph.

    \b
    Examples:
      rulegraph add-rule PHB.attack "When you make an attack roll..." --type mechanic --tag combat
    """
    store = _store(ctx)
    try:
        node = RuleNode(
            rule_id=rule_id,
            text=text,
            node_type=node_type,
            tags=list(tags),
            source=source,
            confidence=confidence,
        )
        store.save_node(node)
        click.echo(f"Added rule  {node.id}  {node.rule_id}  [{node.node_type}]")
    finally:
        store.close()


@main.command("add-edge")
@click.argument("source")
@click.argument("target")
@click.argument("relation")
@click.option("--condition", default="", help="Condition under which this edge applies.")
@click.option("--confidence", type=float, default=1.0, show_default=True)
@click.pass_context
def add_edge(
    ctx: click.Context,
    source: str,
    target: str,
    relation: str,
    condition: str,
    confidence: float,
) -> None:
    """Add an edge between two rules.

    RELATION must be one of: modifies, supersedes, requires, exception-to.

    \b
    Examples:
      rulegraph add-edge PHB.attack PHB.base-attack modifies
      rulegraph add-edge UA.variant PHB.attack supersedes
    """
    store = _store(ctx)
    try:
        edge = RuleEdge(
            source_id=source,
            target_id=target,
            relation=relation,
            condition=condition,
            confidence=confidence,
        )
        store.save_edge(edge)
        click.echo(f"Added edge  {edge.id}  {source} --[{relation}]--> {target}")
    finally:
        store.close()


@main.command("query")
@click.argument("question")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["rich", "json"]),
    default="rich",
    show_default=True,
)
@click.option("--save/--no-save", default=True, show_default=True, help="Save result to DB.")
@click.pass_context
def query_cmd(ctx: click.Context, question: str, fmt: str, save: bool) -> None:
    """Arbitrate a natural-language question against the rule graph.

    \b
    Examples:
      rulegraph query "How do I make an attack roll?"
      rulegraph query "What is difficult terrain?" --format json
    """
    store = _store(ctx)
    try:
        graph = store.load_graph()
        arbiter = RuleArbiter(graph)
        result = arbiter.query(question)
        if save:
            store.save_result(result)
        if fmt == "rich":
            from rich.console import Console

            print_result(result, Console())
        else:
            click.echo(to_json(result=result))
    finally:
        store.close()


@main.command("rules")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--type", "node_type", default=None, help="Filter by node type.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["rich", "json"]),
    default="rich",
    show_default=True,
)
@click.pass_context
def list_rules(
    ctx: click.Context,
    tag: str | None,
    node_type: str | None,
    fmt: str,
) -> None:
    """List rules in the graph.

    \b
    Examples:
      rulegraph rules
      rulegraph rules --tag combat
      rulegraph rules --type mechanic --format json
    """
    store = _store(ctx)
    try:
        graph = store.load_graph()
        rules = graph.find_rules(tag=tag, node_type=node_type)
        if fmt == "rich":
            from rich.console import Console

            print_rules(rules, Console())
        else:
            click.echo(to_json(rules=rules))
    finally:
        store.close()


@main.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show database statistics.

    \b
    Examples:
      rulegraph status
    """
    store = _store(ctx)
    try:
        graph = store.load_graph()
        results = store.list_results()
        click.echo(f"Database:  {store.path}")
        click.echo(f"Rules:     {graph.node_count()} nodes, {graph.edge_count()} edges")
        click.echo(f"Results:   {len(results)} arbitration results stored")
    finally:
        store.close()


@main.command("conflicts")
@click.pass_context
def conflicts_cmd(ctx: click.Context) -> None:
    """Detect rule conflicts and circular dependencies.

    \b
    Examples:
      rulegraph conflicts
      rulegraph --db myrules.db conflicts
    """
    from rulegraph.conflicts import detect_conflicts

    store = _store(ctx)
    try:
        graph = store.load_graph()
        conflicts = detect_conflicts(graph)
        if not conflicts:
            click.echo("No conflicts detected.")
            return
        click.echo(f"Found {len(conflicts)} conflict(s):")
        for c in conflicts:
            click.echo(f"  [{c.severity.upper()}] {c.conflict_type}")
            click.echo(f"    {c.rule_a_id} <-> {c.rule_b_id}")
            click.echo(f"    {c.description}")
    finally:
        store.close()


@main.command("coverage")
@click.argument("queries", nargs=-1)
@click.pass_context
def coverage_cmd(ctx: click.Context, queries: tuple[str, ...]) -> None:
    """Show rule coverage — which rules are queried vs dead.

    Optionally pass queries to test coverage against.

    \b
    Examples:
      rulegraph coverage
      rulegraph coverage "How do I attack?" "What is difficult terrain?"
    """
    from rulegraph.coverage import CoverageTracker

    store = _store(ctx)
    try:
        graph = store.load_graph()
        arbiter = RuleArbiter(graph)
        tracker = CoverageTracker(arbiter)

        if queries:
            for q in queries:
                tracker.arbitrate(q)
        else:
            # Use all stored results to measure historical coverage
            for result in store.list_results():
                for rule_id in result.provenance:
                    tracker._query_counts[rule_id] = tracker._query_counts.get(rule_id, 0) + 1

        report = tracker.report()
        click.echo(f"Total rules:    {report.total_rules}")
        click.echo(f"Rules queried:  {report.rules_queried}")
        click.echo(f"Never queried:  {report.rules_never_queried}")
        click.echo(f"Coverage:       {report.coverage_pct:.1f}%")
        if report.most_used_rules:
            click.echo("Most used:")
            for rule_id, count in report.most_used_rules[:5]:
                click.echo(f"  {rule_id}: {count} query/queries")
        if report.dead_rules:
            click.echo(f"Dead rules ({len(report.dead_rules)}): {', '.join(report.dead_rules[:5])}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
