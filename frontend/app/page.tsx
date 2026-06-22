"use client";
import { useState } from "react";
import { Layout, Typography, notification, Spin, Row, Col } from "antd";
import BacktestForm from "@/components/BacktestForm";
import BacktestResult from "@/components/BacktestResult";
import { runBacktest } from "@/lib/api";
import type { BacktestRequest, BacktestResponse, ApiError } from "@/lib/types";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

export default function BacktestPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [api, contextHolder] = notification.useNotification();

  async function handleSubmit(req: BacktestRequest) {
    setLoading(true);
    setResult(null);
    try {
      const data = await runBacktest(req);
      setResult(data);
    } catch (err) {
      const e = err as ApiError;
      api.error({
        message: "回測失敗",
        description: `[${e.error_code}] ${e.detail}`,
        duration: 6,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {contextHolder}
      <Header style={{ background: "#001529", padding: "0 24px" }}>
        <Title level={4} style={{ color: "#fff", margin: "16px 0 8px" }}>
          AI 雙軌回測 Copilot
        </Title>
        <Text style={{ color: "#aaa", fontSize: 12 }}>
          策略由數學規則執行 · 風控由硬規則把關 · AI 負責分析 · 使用者保留最終決策權
        </Text>
      </Header>
      <Content style={{ padding: 24 }}>
        <Row gutter={24}>
          <Col xs={24} md={8}>
            <BacktestForm onSubmit={handleSubmit} loading={loading} />
          </Col>
          <Col xs={24} md={16}>
            {loading && <Spin size="large" tip="回測進行中…" style={{ marginTop: 80, display: "block" }} />}
            {result && !loading && <BacktestResult data={result} />}
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
