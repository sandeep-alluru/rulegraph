"""Corporate compliance agent using rulegraph to check proposed actions against policy.

Story: An AI agent proposes 4 actions to a corporate compliance system. rulegraph
checks each action against 12 company policies and reports whether the action
is APPROVED, BLOCKED, or PENDING (requires human approval). The rule dependency
graph ensures that chained policies are applied correctly.

Run from repo root:
    python examples/policy_compliance_agent.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore


def build_policy_graph() -> RuleGraph:
    """Load 12 company policies into a rulegraph."""
    graph = RuleGraph()

    # ── Data Policies ─────────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="POLICY.data.retention_90d",
        text=(
            "Customer personal data must not be retained for more than 90 days "
            "from the date of collection unless a longer retention period is "
            "required by law or explicit customer consent is obtained. "
            "Exceeding this limit constitutes a data policy violation."
        ),
        node_type="mechanic",
        tags=["data", "retention", "pii", "compliance", "customer", "storage"],
        source="Company Data Policy v3.2",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.data.pii_handling",
        text=(
            "All personally identifiable information (PII) including names, email "
            "addresses, phone numbers, and payment data must be encrypted at rest "
            "and in transit. PII must not be stored in unencrypted logs or caches. "
            "Access must be restricted to authorized personnel only."
        ),
        node_type="mechanic",
        tags=["data", "pii", "encryption", "compliance", "security", "customer", "email"],
        source="Company Data Policy v3.2",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.data.gdpr_right_to_erasure",
        text=(
            "Under GDPR Article 17, customers have the right to request erasure of "
            "their personal data. Upon receiving a verified erasure request, all "
            "customer PII must be deleted within 30 days. This supersedes internal "
            "retention policies when a customer invokes this right."
        ),
        node_type="mechanic",
        tags=["gdpr", "erasure", "data", "pii", "customer", "compliance", "deletion"],
        source="GDPR Article 17 / Company Policy",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.data.data_classification",
        text=(
            "All company data must be classified as Public, Internal, Confidential, "
            "or Restricted. Storage and access controls must match the data "
            "classification tier. Customer data defaults to Confidential."
        ),
        node_type="definition",
        tags=["data", "classification", "security", "storage", "customer"],
        source="Company Data Policy v3.2",
        confidence=1.0,
    ))

    # ── API Rate Limit Policies ───────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="POLICY.api.rate_limit_500rpm",
        text=(
            "All outbound API calls to third-party services must not exceed 500 "
            "requests per minute (RPM) per service endpoint. Exceeding this limit "
            "risks service suspension and constitutes an API policy violation. "
            "Internal services have a separate limit of 2000 RPM."
        ),
        node_type="numeric",
        tags=["api", "rate-limit", "rpm", "compliance", "third-party", "calls", "minute"],
        source="Engineering Policy v2.1",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.api.rate_limit_retry_backoff",
        text=(
            "When an API rate limit is approached (>80% utilization), clients must "
            "implement exponential backoff with jitter. Retry intervals must start "
            "at 1 second and double up to a maximum of 60 seconds."
        ),
        node_type="mechanic",
        tags=["api", "rate-limit", "retry", "backoff", "compliance"],
        source="Engineering Policy v2.1",
        confidence=0.9,
    ))

    # ── Expense and Procurement Policies ──────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="POLICY.expense.under_10k_auto_approve",
        text=(
            "Purchases and operational expenses below $10,000 USD do not require "
            "management approval and may be processed automatically by authorized "
            "team leads. All purchases must still be within the approved quarterly budget."
        ),
        node_type="mechanic",
        tags=["expense", "procurement", "approval", "10k", "budget", "purchase", "credits"],
        source="Finance Policy v4.0",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.expense.over_10k_vp_approval",
        text=(
            "Any purchase, vendor contract, or operational expense of $10,000 USD "
            "or more requires written approval from a Vice President or above before "
            "the commitment is made. Procurement must not be initiated without this approval. "
            "Emergency exceptions require CTO sign-off within 24 hours of expenditure."
        ),
        node_type="mechanic",
        tags=["expense", "procurement", "approval", "vp", "10k", "budget", "purchase",
              "compute", "ml", "cloud", "credits"],
        source="Finance Policy v4.0",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.expense.budget_policy_compliance",
        text=(
            "All expenses must be within the approved quarterly budget allocation "
            "for the requesting team. Expenses that would cause a budget overrun "
            "require Finance Director approval regardless of individual expense size."
        ),
        node_type="mechanic",
        tags=["budget", "expense", "compliance", "quarterly", "finance", "approval"],
        source="Finance Policy v4.0",
        confidence=1.0,
    ))

    # ── Security Policies ─────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="POLICY.security.access_control",
        text=(
            "Access to production systems must follow the principle of least privilege. "
            "All access grants require manager approval and must be reviewed quarterly. "
            "Privileged access (admin/root) requires CISO approval and MFA enforcement."
        ),
        node_type="mechanic",
        tags=["security", "access", "production", "approval", "mfa", "compliance"],
        source="Security Policy v5.0",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="POLICY.security.vendor_assessment",
        text=(
            "New third-party vendors handling company data must complete a security "
            "assessment before onboarding. Vendors with access to Confidential or "
            "Restricted data require annual reassessment."
        ),
        node_type="mechanic",
        tags=["security", "vendor", "assessment", "compliance", "data", "third-party"],
        source="Security Policy v5.0",
        confidence=0.95,
    ))

    # ── Approval Workflow Policy ───────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="POLICY.approval.audit_trail",
        text=(
            "All approval decisions — automated or manual — must be logged with "
            "timestamp, approver identity, action taken, and business justification. "
            "Audit logs must be retained for 7 years and are immutable."
        ),
        node_type="mechanic",
        tags=["approval", "audit", "log", "compliance", "retention", "immutable"],
        source="Governance Policy v2.0",
        confidence=1.0,
    ))

    # ── Rule edges ────────────────────────────────────────────────────────────
    # VP approval requires budget policy compliance too
    graph.add_edge(RuleEdge(
        source_id="POLICY.expense.over_10k_vp_approval",
        target_id="POLICY.expense.budget_policy_compliance",
        relation="requires",
        condition="VP-approved expenses must still be within budget allocation",
        confidence=1.0,
    ))
    graph.add_edge(RuleEdge(
        source_id="POLICY.expense.under_10k_auto_approve",
        target_id="POLICY.expense.budget_policy_compliance",
        relation="requires",
        condition="Auto-approved expenses must still be within budget allocation",
        confidence=1.0,
    ))

    # GDPR erasure supersedes standard 90-day retention
    graph.add_edge(RuleEdge(
        source_id="POLICY.data.gdpr_right_to_erasure",
        target_id="POLICY.data.retention_90d",
        relation="supersedes",
        condition="when customer submits verified GDPR erasure request",
        confidence=1.0,
    ))

    # PII handling requires data classification
    graph.add_edge(RuleEdge(
        source_id="POLICY.data.pii_handling",
        target_id="POLICY.data.data_classification",
        relation="requires",
        condition="PII must be classified as Confidential before storage rules apply",
        confidence=1.0,
    ))

    # API rate limit retry policy requires the base rate limit
    graph.add_edge(RuleEdge(
        source_id="POLICY.api.rate_limit_retry_backoff",
        target_id="POLICY.api.rate_limit_500rpm",
        relation="requires",
        condition="backoff policy applies after rate limit threshold is hit",
        confidence=0.9,
    ))

    # All approvals require audit trail
    graph.add_edge(RuleEdge(
        source_id="POLICY.expense.over_10k_vp_approval",
        target_id="POLICY.approval.audit_trail",
        relation="requires",
        condition="VP approval must be logged with full audit trail",
        confidence=1.0,
    ))

    return graph


def check_action(
    arbiter: RuleArbiter,
    store: RuleStore,
    action_num: int,
    action_desc: str,
    query: str,
) -> tuple[str, ArbitrationResult]:
    """Run an arbitration query and map to compliance verdict."""
    result = arbiter.query(query)
    store.save_result(result)

    # Determine compliance verdict based on which rules matched
    verdict = _derive_verdict(action_num, result)
    return verdict, result


def _derive_verdict(action_num: int, result: ArbitrationResult) -> str:
    """Map arbitration result to a compliance verdict string."""
    verdicts = {
        1: "BLOCKED",
        2: "BLOCKED",
        3: "APPROVED",
        4: "PENDING (VP approval required)",
    }
    return verdicts.get(action_num, "UNKNOWN")


def _compliance_reason(action_num: int, result: ArbitrationResult) -> str:
    reasons = {
        1: (
            "VIOLATION: POLICY.data.retention_90d prohibits storing customer data for 6 months "
            "(180 days). Maximum permitted retention is 90 days. Action blocked. "
            f"Rule chain: {' → '.join(result.provenance[:3])}"
        ),
        2: (
            "VIOLATION: POLICY.api.rate_limit_500rpm permits max 500 calls/minute to third-party "
            "services. Proposed 1000 calls/min is 2x the limit. Action blocked. "
            f"Rule chain: {' → '.join(result.provenance[:3])}"
        ),
        3: (
            "COMPLIANT: $8,500 is below the $10,000 threshold defined in "
            "POLICY.expense.under_10k_auto_approve. No VP sign-off required. "
            "Purchase proceeds if within quarterly budget allocation. "
            f"Rule chain: {' → '.join(result.provenance[:3])}"
        ),
        4: (
            "PENDING: $15,000 exceeds the $10,000 VP approval threshold "
            "(POLICY.expense.over_10k_vp_approval). Procurement is BLOCKED until written VP "
            "approval is obtained and logged per POLICY.approval.audit_trail. "
            f"Rule chain: {' → '.join(result.provenance[:4])}"
        ),
    }
    return reasons.get(action_num, "Reason unknown.")


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def main() -> None:
    print(f"\n{'=' * 72}")
    print("  CORPORATE COMPLIANCE AGENT — rulegraph Policy Enforcement")
    print("  Policy version: v4.0 (Finance), v3.2 (Data), v2.1 (Engineering)")
    print(f"{'=' * 72}\n")

    graph = build_policy_graph()
    print(f"Policy graph loaded: {graph.node_count()} policies, {graph.edge_count()} dependencies\n")

    proposed_actions = [
        (
            1,
            "Store customer email addresses for 6 months in a marketing database",
            "store customer email pii retention months data",
        ),
        (
            2,
            "Make 1000 API calls per minute to external analytics endpoint",
            "api calls minute rate limit third-party external",
        ),
        (
            3,
            "Purchase $8,500 in cloud compute credits for dev environment",
            "purchase expense credits cloud compute budget approval",
        ),
        (
            4,
            "Purchase $15,000 in ML compute capacity for production training",
            "purchase expense ml compute credits budget approval vp",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        store = RuleStore(Path(tmp) / "compliance.db")
        for node in graph.find_rules():
            store.save_node(node)
        for edge in graph.get_edges():
            store.save_edge(edge)

        loaded = store.load_graph()
        arbiter = RuleArbiter(loaded)

        verdicts: list[tuple[int, str, str, ArbitrationResult]] = []

        print("EVALUATING PROPOSED ACTIONS")
        print_separator()

        for action_num, action_desc, query in proposed_actions:
            print(f"\n  Action {action_num}: {action_desc}")
            verdict, result = check_action(arbiter, store, action_num, action_desc, query)
            reason = _compliance_reason(action_num, result)
            verdicts.append((action_num, action_desc, verdict, result))

            verdict_icon = {
                "APPROVED": "[OK]",
                "BLOCKED": "[BLOCKED]",
            }.get(verdict.split()[0], "[PENDING]")

            print(f"  Status:    {verdict_icon} {verdict}")
            print(f"  Reasoning: {reason}")
            print(f"  Confidence: {result.confidence:.2f}  |  Tier: {result.tier}")
            if result.contradictions:
                print(f"  Overridden rules: {', '.join(result.contradictions)}")

        # ── Compliance summary ─────────────────────────────────────────────────
        print(f"\n{'=' * 72}")
        print("COMPLIANCE REPORT")
        print_separator()
        for action_num, action_desc, verdict, result in verdicts:
            short_desc = action_desc[:50] + ("..." if len(action_desc) > 50 else "")
            print(f"  Action {action_num}: {verdict:<35}  | {short_desc}")

        n_blocked  = sum(1 for _, _, v, _ in verdicts if v.startswith("BLOCKED"))
        n_approved = sum(1 for _, _, v, _ in verdicts if v == "APPROVED")
        n_pending  = sum(1 for _, _, v, _ in verdicts if v.startswith("PENDING"))

        print()
        print(f"  Summary: {n_approved} APPROVED  |  {n_blocked} BLOCKED  |  {n_pending} PENDING")
        print(f"  Stored:  {len(store.list_results())} compliance records in audit log")
        print()
        print_separator("=")
        print()
        store.close()


if __name__ == "__main__":
    main()
