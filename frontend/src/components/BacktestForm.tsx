"use client";
import { useState } from "react";
import {
  Form, Input, InputNumber, Select, DatePicker, Switch, Button, Divider,
} from "antd";
import type { BacktestRequest, GridParams, VAParams } from "@/lib/types";
import dayjs from "dayjs";

interface Props {
  onSubmit: (req: BacktestRequest) => void;
  loading: boolean;
}

export default function BacktestForm({ onSubmit, loading }: Props) {
  const [strategyType, setStrategyType] = useState<"grid" | "value_averaging">("grid");
  const [form] = Form.useForm();

  function handleFinish(values: Record<string, unknown>) {
    const req: BacktestRequest = {
      symbol: values.symbol as string,
      strategy_type: strategyType,
      total_capital: values.total_capital as number,
      start_date: dayjs(values.start_date as string).format("YYYY-MM-DD"),
      end_date: dayjs(values.end_date as string).format("YYYY-MM-DD"),
      market_filter_enabled: values.market_filter_enabled as boolean,
      llm_provider: values.llm_provider as string,
    };
    if (strategyType === "grid") {
      req.grid_params = {
        price_lower: values.price_lower as number,
        price_upper: values.price_upper as number,
        grid_num: values.grid_num as number,
      } as GridParams;
    } else {
      req.va_params = {
        total_periods: values.total_periods as number,
        period_interval_days: values.period_interval_days as number,
      } as VAParams;
    }
    onSubmit(req);
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        symbol: "2330.TW",
        total_capital: 100000,
        market_filter_enabled: true,
        llm_provider: "offline",
        price_lower: 500,
        price_upper: 600,
        grid_num: 6,
        total_periods: 4,
        period_interval_days: 14,
      }}
    >
      <Form.Item label="標的" name="symbol" rules={[{ required: true }]}>
        <Input />
      </Form.Item>

      <Form.Item label="策略">
        <Select
          value={strategyType}
          onChange={(v) => setStrategyType(v)}
          options={[
            { label: "網格交易", value: "grid" },
            { label: "價值平均", value: "value_averaging" },
          ]}
        />
      </Form.Item>

      <Form.Item label="總資金" name="total_capital" rules={[{ required: true }]}>
        <InputNumber min={1000} step={1000} style={{ width: "100%" }} />
      </Form.Item>

      <Form.Item label="開始日期" name="start_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>

      <Form.Item label="結束日期" name="end_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>

      <Form.Item label="LLM Provider" name="llm_provider">
        <Select
          options={[
            { label: "離線（規則）", value: "offline" },
            { label: "Claude", value: "claude" },
            { label: "OpenAI", value: "openai" },
            { label: "Gemini", value: "gemini" },
            { label: "Ollama", value: "ollama" },
          ]}
        />
      </Form.Item>

      <Form.Item label="啟用大盤 60MA 濾網" name="market_filter_enabled" valuePropName="checked">
        <Switch />
      </Form.Item>

      <Divider />

      {strategyType === "grid" ? (
        <>
          <Form.Item label="區間下限" name="price_lower" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="區間上限" name="price_upper" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="網格層數" name="grid_num" rules={[{ required: true }]}>
            <InputNumber min={1} max={12} style={{ width: "100%" }} />
          </Form.Item>
        </>
      ) : (
        <>
          <Form.Item label="總扣款次數" name="total_periods" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="每期間隔天數" name="period_interval_days" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
        </>
      )}

      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          驗證並回測
        </Button>
      </Form.Item>
    </Form>
  );
}
