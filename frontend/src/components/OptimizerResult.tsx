"use client";
import { Table, Card, Statistic, Row, Col, Tag, Typography } from "antd";
import type { OptimizeResponse, RoundResult } from "@/lib/types";

const { Title } = Typography;

interface Props {
  data: OptimizeResponse;
}

export default function OptimizerResult({ data }: Props) {
  const columns = [
    {
      title: "來源",
      dataIndex: "round_num",
      key: "source",
      render: (v: number) =>
        v === 0 ? <Tag color="blue">Phase 1 全搜尋</Tag> : <Tag color="purple">Phase 2 LLM 輪次 {v}</Tag>,
    },
    {
      title: "Score",
      dataIndex: "score",
      key: "score",
      render: (v: number) => v.toFixed(4),
      sorter: (a: RoundResult, b: RoundResult) => b.score - a.score,
    },
    { title: "報酬率", dataIndex: "total_return", key: "total_return", render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { title: "MDD", dataIndex: "mdd", key: "mdd", render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { title: "勝率", dataIndex: "win_rate", key: "win_rate", render: (v: number) => `${(v * 100).toFixed(0)}%` },
    { title: "交易數", dataIndex: "trade_count", key: "trade_count" },
  ];

  return (
    <div style={{ marginTop: 24 }}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic title="最佳 Score" value={data.best_score.toFixed(4)} />
        </Col>
        <Col span={8}>
          <Statistic title="停止原因" value={data.stopped_reason} />
        </Col>
      </Row>

      <Card title="最佳參數" style={{ marginBottom: 16 }}>
        <pre style={{ margin: 0 }}>{JSON.stringify(data.best_params, null, 2)}</pre>
      </Card>

      <Title level={5}>所有輪次結果</Title>
      <Table
        dataSource={data.all_rounds}
        columns={columns}
        rowKey={(r: RoundResult) => `${r.round_num}-${r.score}`}
        size="small"
        pagination={false}
      />
    </div>
  );
}
