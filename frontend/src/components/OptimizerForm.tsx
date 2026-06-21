"use client";
import { Form, Input, InputNumber, Select, DatePicker, Button } from "antd";
import type { OptimizeRequest } from "@/lib/types";
import dayjs from "dayjs";

interface Props {
  onSubmit: (req: OptimizeRequest) => void;
  loading: boolean;
}

export default function OptimizerForm({ onSubmit, loading }: Props) {
  const [form] = Form.useForm();

  function handleFinish(values: Record<string, unknown>) {
    const req: OptimizeRequest = {
      symbol: values.symbol as string,
      strategy_type: values.strategy_type as "grid" | "value_averaging",
      total_capital: values.total_capital as number,
      start_date: dayjs(values.start_date as string).format("YYYY-MM-DD"),
      end_date: dayjs(values.end_date as string).format("YYYY-MM-DD"),
      max_rounds: values.max_rounds as number,
      llm_provider: values.llm_provider as string,
      search_space: {
        price_lower: (values.price_lower as string).split(",").map(Number),
        price_upper: (values.price_upper as string).split(",").map(Number),
        grid_num: (values.grid_num as string).split(",").map(Number),
      },
    };
    onSubmit(req);
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        symbol: "2330.TW",
        strategy_type: "grid",
        total_capital: 100000,
        max_rounds: 3,
        llm_provider: "offline",
        price_lower: "500,510,520",
        price_upper: "580,590,600",
        grid_num: "4,6,8",
      }}
    >
      <Form.Item label="標的" name="symbol" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="策略" name="strategy_type">
        <Select options={[
          { label: "網格交易", value: "grid" },
          { label: "價值平均", value: "value_averaging" },
        ]} />
      </Form.Item>
      <Form.Item label="總資金" name="total_capital">
        <InputNumber min={1000} step={1000} style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="開始日期" name="start_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="結束日期" name="end_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="LLM Provider" name="llm_provider">
        <Select options={[
          { label: "離線（規則）", value: "offline" },
          { label: "Claude", value: "claude" },
          { label: "OpenAI", value: "openai" },
        ]} />
      </Form.Item>
      <Form.Item label="LLM 精細輪數" name="max_rounds">
        <InputNumber min={0} max={10} style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="price_lower 候選（逗號分隔）" name="price_lower">
        <Input />
      </Form.Item>
      <Form.Item label="price_upper 候選（逗號分隔）" name="price_upper">
        <Input />
      </Form.Item>
      <Form.Item label="grid_num 候選（逗號分隔）" name="grid_num">
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          啟動優化
        </Button>
      </Form.Item>
    </Form>
  );
}
