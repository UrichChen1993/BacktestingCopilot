"use client";
import { useState } from "react";
import { Layout, Typography, notification, Spin, Row, Col } from "antd";
import OptimizerForm from "@/components/OptimizerForm";
import OptimizerResult from "@/components/OptimizerResult";
import { runOptimize } from "@/lib/api";
import type { OptimizeRequest, OptimizeResponse, ApiError } from "@/lib/types";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

export default function OptimizePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [api, contextHolder] = notification.useNotification();

  async function handleSubmit(req: OptimizeRequest) {
    setLoading(true);
    setResult(null);
    try {
      const data = await runOptimize(req);
      setResult(data);
    } catch (err) {
      const e = err as ApiError;
      api.error({
        message: "優化失敗",
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
          AI 雙軌回測 Copilot — 自動優化
        </Title>
        <Text style={{ color: "#aaa", fontSize: 12 }}>
          Phase 1 全搜尋 + Phase 2 LLM 精細搜尋
        </Text>
      </Header>
      <Content style={{ padding: 24 }}>
        <Row gutter={24}>
          <Col xs={24} md={8}>
            <OptimizerForm onSubmit={handleSubmit} loading={loading} />
          </Col>
          <Col xs={24} md={16}>
            {loading && <Spin size="large" tip="優化進行中…" style={{ marginTop: 80, display: "block" }} />}
            {result && !loading && <OptimizerResult data={result} />}
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
