"""CSV and Markdown exporters for backtest output."""

from __future__ import annotations

import csv
import io

from ..models import BacktestResult, Trade


def trades_to_csv(trades: list[Trade]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "side", "price", "quantity", "amount", "fee", "tax", "reason"])
    for t in trades:
        writer.writerow(
            [t.day.isoformat(), t.side.value, t.price, t.quantity, t.amount, t.fee, t.tax, t.reason]
        )
    return buf.getvalue()


def result_to_markdown(result: BacktestResult) -> str:
    lines = [
        f"# 回測報告 — {result.symbol} ({result.strategy_type.value})",
        "",
        f"- 期間：{result.start_date} ~ {result.end_date}",
        f"- 初始資金：{result.initial_capital:,.0f}",
        f"- 期末總資產：{result.final_value:,.0f}",
        f"- 總報酬率：{result.total_return:.2%}",
        f"- 最大回撤 (MDD)：{result.mdd:.2%}",
        f"- 已實現損益：{result.realized_profit:,.0f}",
        f"- 未實現損益：{result.unrealized_profit:,.0f}",
        f"- 交易次數：{result.trade_count}",
        f"- 勝率：{result.win_rate:.0%}",
        f"- 資金使用率：{result.cash_usage_rate:.0%}",
        f"- 剩餘現金：{result.remaining_cash:,.0f}",
        f"- 剩餘持股：{result.holding_quantity}",
        f"- 平均成本：{result.avg_cost:,.2f}",
        f"- 風控觸發次數：{result.market_filter_count}",
    ]
    return "\n".join(lines) + "\n"
