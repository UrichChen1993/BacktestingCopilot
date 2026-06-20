"use client";
import {
  Row, Col, Statistic, Alert, Table, Tag, Typography, Card, Divider, Button,
} from "antd";
import { Line } from "@ant-design/charts";
import type { BacktestResponse, TradeRow } from "@/lib/types";

const { Title, Paragraph } = Typography;

interface Props {
  data: BacktestResponse;
}

export default function BacktestResult({ data }: Props) {
  const equityData = data.equity_curve.map((p) => ({
    date: p.date,
    value: p.value,
  }));

  const lineConfig = {
    data: equityData,
    xField: "date",
    yField: "value",
    smooth: true,
    height: 260,
  };

  const tradeColumns = [
    { title: "日期", dataIndex: "day", key: "day" },
    {
      title: "方向",
      dataIndex: "side",
      key: "side",
      render: (v: string) => (
        <Tag color={v === "BUY" ? "green" : "red"}>{v}</Tag>
      ),
    },
    { title: "價格", dataIndex: "price", key: "price" },
    { title: "數量", dataIndex: "quantity", key: "quantity" },
    { title: "金額", dataIndex: "amount", key: "amount" },
    { title: "備註", dataIndex: "reason", key: "reason" },
  ];

  function downloadFile(content: string, filename: string, mime: string) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const riskColor =
    data.risk_level === "LOW" ? "success" :
    data.risk_level === "MEDIUM" ? "warning" : "error";

  return (
    <div style={{ marginTop: 24 }}>
      {data.warnings.map((w, i) => (
        <Alert key={i} type="warning" message={w} style={{ marginBottom: 8 }} />
      ))}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="總報酬率" value={(data.total_return * 100).toFixed(2)} suffix="%" /></Col>
        <Col span={6}><Statistic title="最大回撤 MDD" value={(data.mdd * 100).toFixed(2)} suffix="%" /></Col>
        <Col span={6}><Statistic title="勝率" value={(data.win_rate * 100).toFixed(0)} suffix="%" /></Col>
        <Col span={6}><Statistic title="交易次數" value={data.trade_count} /></Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="期末總資產" value={data.final_value.toFixed(0)} /></Col>
        <Col span={6}><Statistic title="已實現損益" value={data.realized_profit.toFixed(0)} /></Col>
        <Col span={6}><Statistic title="未實現損益" value={data.unrealized_profit.toFixed(0)} /></Col>
        <Col span={6}><Statistic title="風控觸發次數" value={data.market_filter_count} /></Col>
      </Row>

      {equityData.length > 0 && (
        <Card title="權益曲線" style={{ marginBottom: 16 }}>
          <Line {...lineConfig} />
        </Card>
      )}

      <Card title="AI 回測分析" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Alert type={riskColor} message={`風險等級：${data.risk_level}`} />
          </Col>
          <Col span={6}>
            <Alert
              type={data.paper_trading_ready ? "success" : "warning"}
              message={data.paper_trading_ready ? "✅ Paper Trading 就緒" : "⚠️ 尚未就緒"}
            />
          </Col>
        </Row>
        <Paragraph style={{ marginTop: 12 }}>{data.summary}</Paragraph>
        <ul>
          {data.suggestions.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
        {data.narrative && (
          <Alert type="info" message={`🤖 AI 敘述：${data.narrative}`} style={{ marginTop: 8 }} />
        )}
      </Card>

      <Divider />

      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col>
          <Button onClick={() => downloadFile(data.trades_csv, "trades.csv", "text/csv")}>
            下載交易明細 CSV
          </Button>
        </Col>
        <Col>
          <Button onClick={() => downloadFile(data.report_md, "report.md", "text/markdown")}>
            下載回測報告 Markdown
          </Button>
        </Col>
      </Row>

      <Title level={5}>交易明細</Title>
      <Table
        dataSource={data.trades}
        columns={tradeColumns}
        rowKey={(r: TradeRow) => `${r.day}-${r.side}-${r.price}`}
        size="small"
        pagination={{ pageSize: 20 }}
      />
    </div>
  );
}
