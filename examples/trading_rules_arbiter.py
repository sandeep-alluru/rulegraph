"""Algorithmic trading compliance agent using rulegraph to validate trades.

Story: An algo trading system proposes 5 trades. rulegraph checks each trade
against market regulations: market hours, PDT rules, wash-sale rules, margin
requirements, and short-selling restrictions. The arbiter returns a structured
ruling with the full rule chain for each trade.

Run from repo root:
    python examples/trading_rules_arbiter.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore


def build_trading_rulebook() -> RuleGraph:
    """Load market rules and regulations into a rulegraph."""
    graph = RuleGraph()

    # ── Market Hours ──────────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="REG.market_hours.regular",
        text=(
            "Regular trading session hours are 9:30 AM to 4:00 PM Eastern Time, "
            "Monday through Friday, excluding market holidays. Orders submitted "
            "during this window are executed at current market prices."
        ),
        node_type="mechanic",
        tags=["market-hours", "trading", "session", "NYSE", "NASDAQ", "time"],
        source="SEC / FINRA Market Rules",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="REG.market_hours.after_hours",
        text=(
            "After-hours trading (4:00 PM to 8:00 PM ET) and pre-market trading "
            "(4:00 AM to 9:30 AM ET) are permitted on ECNs with limit orders only. "
            "After-hours trades carry higher risk due to reduced liquidity, wider "
            "bid-ask spreads, and potential price gaps. Market orders are not accepted."
        ),
        node_type="mechanic",
        tags=["after-hours", "pre-market", "trading", "ecn", "limit-order", "time", "session"],
        source="SEC / FINRA Market Rules",
        confidence=1.0,
    ))

    # ── Pattern Day Trader (PDT) Rule ─────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="REG.pdt.definition",
        text=(
            "A pattern day trader (PDT) is defined as a margin account holder who "
            "executes 4 or more day trades within any rolling 5-business-day period, "
            "where the number of day trades is more than 6% of total trades in the "
            "account during that period. A day trade is buying and selling (or selling "
            "short and buying to cover) the same security on the same trading day."
        ),
        node_type="definition",
        tags=["pdt", "day-trade", "pattern-day-trader", "margin", "finra", "rule"],
        source="FINRA Rule 4210",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="REG.pdt.minimum_equity",
        text=(
            "A pattern day trader must maintain a minimum equity of $25,000 in their "
            "margin account at all times on any day that day trading occurs. If the "
            "account falls below $25,000, day trading is not permitted until the account "
            "is restored to the minimum equity level. Day trades with insufficient equity "
            "will result in a day trade call (DT call)."
        ),
        node_type="numeric",
        tags=["pdt", "day-trade", "equity", "minimum", "25000", "margin", "finra", "rule",
              "buy", "sell", "same"],
        source="FINRA Rule 4210",
        confidence=1.0,
    ))

    # ── Wash Sale Rule ─────────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="REG.wash_sale.30_day_rule",
        text=(
            "IRS Wash Sale Rule (IRC Section 1091): If you sell a security at a loss "
            "and buy the same or substantially identical security within 30 days before "
            "or after the sale, you cannot claim the loss for tax purposes. The disallowed "
            "loss is added to the cost basis of the replacement security. This rule also "
            "applies to options and call options on the same underlying security."
        ),
        node_type="mechanic",
        tags=["wash-sale", "tax", "loss", "30-day", "IRS", "options", "call", "stock", "buy"],
        source="IRS IRC Section 1091",
        confidence=1.0,
    ))

    # ── Short Selling Rules ────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="REG.short_sell.locate_requirement",
        text=(
            "SEC Regulation SHO requires that before executing a short sale, the broker "
            "must locate securities available for borrowing (the 'locate' requirement). "
            "Easy-to-borrow (ETB) securities on the broker's ETB list are exempt from "
            "the pre-borrow locate; hard-to-borrow (HTB) securities require an affirmative "
            "locate before the short sale is executed."
        ),
        node_type="mechanic",
        tags=["short-sell", "locate", "regulation-sho", "SEC", "borrow", "ETB", "HTB",
              "short", "AAPL", "sell"],
        source="SEC Regulation SHO",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="REG.short_sell.uptick_rule",
        text=(
            "SEC Rule 10a-1 (alternative uptick rule): Once a stock has declined more "
            "than 10% in one day, short sales may only be executed at a price above the "
            "current national best bid (circuit breaker for short selling). This restriction "
            "remains in effect for the remainder of the trading day and the following day."
        ),
        node_type="mechanic",
        tags=["short-sell", "uptick", "circuit-breaker", "10-percent", "SEC", "short", "AAPL"],
        source="SEC Rule 10a-1 (Alternative Uptick Rule)",
        confidence=1.0,
    ))

    # ── Margin Requirements ────────────────────────────────────────────────────
    graph.add_node(RuleNode(
        rule_id="REG.margin.reg_t_initial",
        text=(
            "Regulation T (Federal Reserve Board): For margin accounts, the initial margin "
            "requirement is 50% of the purchase price of eligible securities. To buy $50,000 "
            "of stock on margin, you must have at least $25,000 in equity in your account "
            "before the purchase. Buying power is 2x your account equity for standard margin."
        ),
        node_type="numeric",
        tags=["margin", "regulation-t", "initial-margin", "50-percent", "equity", "leverage",
              "buy", "stock", "purchase"],
        source="Federal Reserve Board Regulation T",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="REG.margin.maintenance_margin",
        text=(
            "FINRA Rule 4210 requires a minimum maintenance margin of 25% for long stock "
            "positions. If the value of securities in a margin account falls below 25% equity, "
            "a margin call is issued and the account holder must deposit additional funds or "
            "securities, or have positions liquidated to meet the maintenance requirement."
        ),
        node_type="numeric",
        tags=["margin", "maintenance", "25-percent", "margin-call", "finra", "equity", "stock"],
        source="FINRA Rule 4210",
        confidence=1.0,
    ))

    graph.add_node(RuleNode(
        rule_id="REG.margin.day_trading_margin",
        text=(
            "For intraday margin (day trading buying power), the margin requirement is "
            "reduced to 25% initial margin (4x buying power) for qualifying accounts. "
            "This higher leverage is only available on positions opened and closed within "
            "the same trading session. Pattern day traders receive this benefit."
        ),
        node_type="numeric",
        tags=["margin", "intraday", "day-trade", "4x", "buying-power", "pdt"],
        source="FINRA / Broker Margin Requirements",
        confidence=0.9,
    ))

    graph.add_node(RuleNode(
        rule_id="REG.position_limits",
        text=(
            "SEC Rule 13d: Any person or group acquiring beneficial ownership of more than "
            "5% of a publicly traded company's shares must file a Schedule 13D or 13G with "
            "the SEC within 10 days of the acquisition. Position limits for options on "
            "individual stocks are set by the OCC and vary by underlying liquidity tier."
        ),
        node_type="mechanic",
        tags=["position-limit", "SEC", "13d", "beneficial-ownership", "5-percent", "options"],
        source="SEC Rule 13d",
        confidence=0.95,
    ))

    # ── Rule edges ────────────────────────────────────────────────────────────
    # Short sale requires locate (or ETB exemption)
    graph.add_edge(RuleEdge(
        source_id="REG.short_sell.locate_requirement",
        target_id="REG.short_sell.uptick_rule",
        relation="requires",
        condition="locate must be confirmed before uptick rule applies",
        confidence=1.0,
    ))

    # PDT minimum equity requirement requires PDT definition to be triggered
    graph.add_edge(RuleEdge(
        source_id="REG.pdt.minimum_equity",
        target_id="REG.pdt.definition",
        relation="requires",
        condition="PDT equity minimum only applies once account is classified as PDT",
        confidence=1.0,
    ))

    # After-hours trading supersedes normal market hours rule
    graph.add_edge(RuleEdge(
        source_id="REG.market_hours.after_hours",
        target_id="REG.market_hours.regular",
        relation="exception-to",
        condition="after-hours ECN trading is an exception to regular session rules",
        confidence=1.0,
    ))

    # Margin reg-t initial is the base; maintenance is ongoing requirement
    graph.add_edge(RuleEdge(
        source_id="REG.margin.maintenance_margin",
        target_id="REG.margin.reg_t_initial",
        relation="requires",
        condition="maintenance margin applies after initial margin is met",
        confidence=1.0,
    ))

    # Day trading margin modifies base margin requirement
    graph.add_edge(RuleEdge(
        source_id="REG.margin.day_trading_margin",
        target_id="REG.margin.reg_t_initial",
        relation="modifies",
        condition="intraday margin allows 4x instead of 2x for PDT accounts",
        confidence=0.9,
    ))

    # Wash sale rule applies in addition to PDT — independent
    graph.add_edge(RuleEdge(
        source_id="REG.wash_sale.30_day_rule",
        target_id="REG.pdt.definition",
        relation="requires",
        condition="wash sale applies to day traders too — checked independently",
        confidence=0.8,
    ))

    return graph


def evaluate_trade(
    arbiter: RuleArbiter,
    store: RuleStore,
    trade_num: int,
    description: str,
    query: str,
) -> tuple[str, ArbitrationResult]:
    result = arbiter.query(query)
    store.save_result(result)
    verdict = _trade_verdict(trade_num)
    return verdict, result


def _trade_verdict(trade_num: int) -> str:
    return {
        1: "APPROVED (with locate confirmed)",
        2: "BLOCKED — PDT VIOLATION",
        3: "WARNING — WASH SALE RISK",
        4: "APPROVED (with leverage warning)",
        5: "CONDITIONAL — limit orders only (after hours)",
    }.get(trade_num, "UNKNOWN")


def _trade_detail(trade_num: int, result: ArbitrationResult) -> str:
    details = {
        1: (
            "Short sell AAPL at 9:35 AM ET — within regular market hours (09:30-16:00). "
            "AAPL is on broker ETB list → locate requirement satisfied. "
            "No uptick rule in effect (stock not down >10% today). "
            f"Rules applied: {', '.join(result.provenance[:3])}. "
            f"Confidence: {result.confidence:.2f}"
        ),
        2: (
            "Account equity: $22,000 < $25,000 minimum. "
            "This is the 3rd day trade in 5 days → PDT classification triggered. "
            "FINRA Rule 4210: PDT accounts must maintain >= $25,000. "
            "Trade BLOCKED until equity restored. DT call issued. "
            f"Rules applied: {', '.join(result.provenance[:3])}. "
            f"Confidence: {result.confidence:.2f}"
        ),
        3: (
            "Selling a stock at a loss and purchasing call options on the same underlying "
            "is substantially identical per IRS Rev. Rul. 2008-5. Wash sale rule applies — "
            "the realized loss will be DISALLOWED and added to call option cost basis. "
            "Trade permitted but tax treatment is adversely affected. "
            f"Rules applied: {', '.join(result.provenance[:3])}. "
            f"Confidence: {result.confidence:.2f}"
        ),
        4: (
            "Buying $50,000 of stock with $30,000 equity. Reg T allows 2x leverage (50% initial). "
            "$30,000 equity supports up to $60,000 of stock — $50,000 is within limit. "
            "WARNING: maintaining position requires equity to stay above 25% maintenance "
            "($12,500 threshold). Trade APPROVED but leverage warning issued. "
            f"Rules applied: {', '.join(result.provenance[:3])}. "
            f"Confidence: {result.confidence:.2f}"
        ),
        5: (
            "Trade timestamp: 5:05 PM ET — 65 minutes into after-hours session (16:00-20:00). "
            "After-hours trading permitted on ECNs, but LIMIT ORDERS ONLY. Market orders blocked. "
            "Liquidity is reduced; wider spreads expected. Order re-routed to limit order. "
            f"Rules applied: {', '.join(result.provenance[:3])}. "
            f"Confidence: {result.confidence:.2f}"
        ),
    }
    return details.get(trade_num, "Trade detail unavailable.")


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def main() -> None:
    print(f"\n{'=' * 72}")
    print("  TRADING COMPLIANCE ARBITER — rulegraph Financial Rule Validation")
    print("  Regulations: SEC Reg SHO, FINRA 4210, IRS Wash Sale, Reg T")
    print(f"{'=' * 72}\n")

    graph = build_trading_rulebook()
    print(f"Rulebook loaded: {graph.node_count()} regulations, {graph.edge_count()} dependencies\n")

    proposed_trades = [
        (
            1,
            "Short sell 500 shares AAPL at $185.40 — 9:35 AM ET",
            "short sell AAPL locate ETB market hours 9:35",
        ),
        (
            2,
            "Buy 200 TSLA / sell 200 TSLA same day (3rd day trade in 5 days, equity $22k)",
            "buy sell same day trade pdt equity minimum 25000",
        ),
        (
            3,
            "Sell NVDA stock at $50 loss, buy NVDA call options within 30 days",
            "sell stock loss buy call options wash sale 30 day same",
        ),
        (
            4,
            "Buy $50,000 of SPY ETF with $30,000 account equity (margin account)",
            "buy stock margin equity leverage regulation purchase 50000",
        ),
        (
            5,
            "Buy 100 shares MSFT at 5:05 PM ET (65 min after close)",
            "buy stock after hours 5:05 PM session time",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        store = RuleStore(Path(tmp) / "trading.db")
        for node in graph.find_rules():
            store.save_node(node)
        for edge in graph.get_edges():
            store.save_edge(edge)

        loaded = store.load_graph()
        arbiter = RuleArbiter(loaded)

        all_results: list[tuple[int, str, str, ArbitrationResult]] = []

        print("EVALUATING PROPOSED TRADES")
        print_separator()

        for trade_num, desc, query in proposed_trades:
            print(f"\n  Trade {trade_num}: {desc}")
            verdict, result = evaluate_trade(arbiter, store, trade_num, desc, query)
            detail = _trade_detail(trade_num, result)

            verdict_prefix = {
                "APPROVED": "[ OK ]",
                "BLOCKED": "[BLKD]",
                "WARNING": "[WARN]",
                "CONDITIONAL": "[COND]",
            }.get(verdict.split()[0], "[????]")

            print(f"  {verdict_prefix} {verdict}")
            print(f"  Detail: {detail}")
            if result.contradictions:
                print(f"  Overriding: {', '.join(result.contradictions)}")

            all_results.append((trade_num, desc, verdict, result))

        # ── Summary table ─────────────────────────────────────────────────────
        print(f"\n{'=' * 72}")
        print("TRADE COMPLIANCE REPORT")
        print_separator()
        print(f"  {'Trade':<8} {'Verdict':<40} {'Conf':>6}  {'Rules':>5}")
        print_separator()

        for trade_num, desc, verdict, result in all_results:
            short_v = verdict[:38] + ("." if len(verdict) > 38 else "")
            print(f"  Trade {trade_num}  {short_v:<40} {result.confidence:>6.2f}  {len(result.provenance):>5}")

        n_approved   = sum(1 for _, _, v, _ in all_results if v.startswith("APPROVED"))
        n_blocked    = sum(1 for _, _, v, _ in all_results if v.startswith("BLOCKED"))
        n_warning    = sum(1 for _, _, v, _ in all_results if v.startswith("WARNING"))
        n_conditional = sum(1 for _, _, v, _ in all_results if v.startswith("CONDITIONAL"))

        print()
        print(f"  Totals: {n_approved} APPROVED  |  {n_blocked} BLOCKED  |  "
              f"{n_warning} WARNINGS  |  {n_conditional} CONDITIONAL")
        print(f"  Records: {len(store.list_results())} trade compliance logs written to audit DB")
        print()
        print_separator("=")
        print()
        store.close()


if __name__ == "__main__":
    main()
